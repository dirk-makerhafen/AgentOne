"""Session-wide fence for in-flight compaction.

A compaction is a *session* event, not just a step inside one turn: while the
summary fork runs, no other root in the same chat session may append chat
messages.  The flags live on ``SessionModel`` so every Celery worker sees them,
and the live ``compact_turn`` call id makes release/cancellation exact.
"""
# Local imports here avoid cycles between runtime, models and task scheduling.
# pylint: disable=import-outside-toplevel
from __future__ import annotations

from typing import Any

from runtime.context_manager import ContextTracker


class CompactionInProgress(Exception):
    """Raised when a chat message would be written during compaction.

    Only the compaction/reflection machinery is allowed through the fence;
    ordinary turns must wait until the ``compact_turn`` call has ended.
    """


_COMPACTION_WRITE_TASKS = frozenset({"ingest_compaction", "ingest_reflection_result"})
_SLASH_CHAIN_TASKS = frozenset({
    "ingest_slash_command", "process_slashcommand", "handle_slashcommand_response",
})


def _type_value(message_type: Any) -> Any:
    return getattr(message_type, "value", message_type)


def _run_info(run: Any = None) -> tuple[str | None, int | None]:
    """Return ``(task_name, session_root_task_id)`` for the current run."""
    if run is None:
        run = ContextTracker.current
    call = getattr(run, "agent_task_call", None) if run is not None else None
    version = getattr(run, "task_definition_version", None) if run is not None else None
    definition = getattr(version, "task_definition", None) if version is not None else None
    return (
        getattr(definition, "name", None),
        getattr(call, "session_root_task_id", None),
    )


def current_root_id(session: Any = None) -> int | None:
    """Root call id of the work currently executing in *session*, if any.

    Used to open the fence *before* the ``compact_turn`` call exists so a
    sibling turn cannot slip a message into the short dispatch window.
    """
    run = getattr(session, "_current_taskrun", None) if session is not None else None
    if run is None:
        run = ContextTracker.current
    _, root_id = _run_info(run)
    return root_id


def compaction_state(session_id: int | None) -> tuple[bool, int | None, int | None]:
    """Fresh-DB ``(active, compacting_call_id, compacting_root_task_id)``.

    A stale flag whose call has already ended is cleared lazily.  This covers
    worker crashes and force-fail paths that never reached the normal
    ``_on_taskcall_ended`` cleanup.
    """
    if not session_id:
        return False, None, None
    from server.models.enums.task_enums import TaskCallStatus
    from server.models.sessions.session import SessionModel
    from server.models.tasks.agent_task_call import AgentTaskCall

    row = (
        SessionModel.objects.filter(pk=session_id)
        .values_list("is_compacting", "compacting_call_id", "compacting_root_task_id")
        .first()
    )
    if not row or not row[0]:
        return False, None, None

    _active, call_id, root_id = row
    if call_id:
        status = (
            AgentTaskCall.objects.filter(pk=call_id)
            .values_list("status", flat=True)
            .first()
        )
        if status is None or status == TaskCallStatus.ENDED:
            end_compaction(session_id, call_id=call_id)
            return False, None, None
    return True, call_id, root_id


def try_begin_compaction(
    session: Any,
    root_call_id: int | None = None,
) -> bool:
    """Atomically open the fence; return False if another compaction owns it.

    Stale flags (whose call has already ended) are cleared first, so a worker
    crash cannot permanently wedge the session.  Callers that lose the race
    must not dispatch a second compaction fork.
    """
    session_id = session.model.pk
    # Drop a stale flag before attempting to acquire.
    compaction_state(session_id)
    model = _session_model()
    updated = model.atomic_update_by_pk(
        session_id,
        expect={"is_compacting": False},
        is_compacting=True,
        compacting_call_id=None,
        compacting_root_task_id=root_call_id,
    )
    _sync_session_model(session)
    return bool(updated)


def begin_compaction(
    session: Any,
    root_call_id: int | None = None,
    call_id: int | None = None,
) -> None:
    """Open the fence unconditionally (test/setup helper)."""
    session_id = session.model.pk
    model = _session_model()
    model.atomic_update_by_pk(
        session_id,
        is_compacting=True,
        compacting_call_id=call_id,
        compacting_root_task_id=root_call_id,
    )
    # Keep the in-memory copy aligned for code that reads it in this worker.
    _sync_session_model(session)


def _sync_session_model(session: Any) -> None:
    """Refresh the in-memory session row from the DB after a fence change."""
    try:
        session.model.refresh_from_db(
            fields=["is_compacting", "compacting_call_id", "compacting_root_task_id"]
        )
    except Exception:  # pylint: disable=broad-exception-caught
        pass


def set_compaction_call(session: Any, call: Any) -> None:
    """Retarget the fence at a (possibly retried) ``compact_turn`` call."""
    session_id = session.model.pk
    call_id = getattr(call, "pk", None)
    root_id = getattr(call, "session_root_task_id", None)
    _session_model().atomic_update_by_pk(
        session_id,
        is_compacting=True,
        compacting_call_id=call_id,
        compacting_root_task_id=root_id,
    )
    _sync_session_model(session)


def end_compaction(session_id: int | None, call_id: int | None = None) -> None:
    """Close the fence, optionally only when it still points at *call_id*."""
    if not session_id:
        return
    expect = {"compacting_call_id": call_id} if call_id is not None else None
    _session_model().atomic_update_by_pk(
        session_id,
        expect=expect,
        is_compacting=False,
        compacting_call_id=None,
        compacting_root_task_id=None,
    )


def stop_other_roots(session: Any, keep_root_id: int | None) -> int:
    """Stop every live root in this session except *keep_root_id*.

    Compaction supersedes the conversation and tool work that led to it.  A
    sibling root that already started an LLM turn would otherwise persist its
    assistant message after the compaction started, interleaving chat history
    with the summary boundary.  Returns the number of roots stopped.
    """
    if keep_root_id is None:
        # Direct/test invocation without a run context: never guess which
        # roots are "other" — cancelling all of them would be unsafe.
        return 0

    from server.models.enums.task_enums import TaskCallStatus
    from server.models.tasks.agent_task_call import AgentTaskCall
    from runtime.tasks.call_scheduler import CallScheduler

    root_ids = list(
        AgentTaskCall.objects.filter(session_id=session.model.pk)
        .exclude(status=TaskCallStatus.ENDED)
        .exclude(session_root_task_id=keep_root_id)
        .exclude(session_root_task_id__isnull=True)
        .values_list("session_root_task_id", flat=True)
        .distinct()
    )
    for root_id in root_ids:
        if root_id and root_id != keep_root_id:
            CallScheduler.cancel_root_tasktree(root_id)
    return len(root_ids)


def check_message_write(session_id: int, message_type: Any, run: Any = None) -> None:
    """Block non-compaction message inserts while the session is compacting."""
    active, _call_id, root_id = compaction_state(session_id)
    if not active:
        return

    task_name, current_root = _run_info(run)
    msg_type = _type_value(message_type)
    info_type = _type_value(_message_type_enum().INFO)

    if task_name in _COMPACTION_WRITE_TASKS:
        # The marker, the started/success/failure toasts, and the detached
        # reflection report all land through their own ingest scripts.
        return
    if task_name == "ingest_user_message" and msg_type == info_type and current_root == root_id:
        # The "Compaction started" INFO notice is written via add_user_message,
        # so it arrives as an ordinary ingest call in the compaction root.
        return
    if task_name in _SLASH_CHAIN_TASKS and current_root == root_id:
        # /compact's own command + response messages belong to the compacting
        # root and must be recorded even though the fence is already open.
        return

    raise CompactionInProgress(
        f"session {session_id} is compacting; message writes are paused "
        f"(task={task_name}, type={msg_type})"
    )


def _session_model() -> Any:
    from server.models.sessions.session import SessionModel

    return SessionModel


def _message_type_enum() -> Any:
    from server.models.enums.message_enums import MessageType
    return MessageType
