from __future__ import annotations

from datetime import datetime
from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message


#: Total compaction attempts per trigger (initial fork + retries).  Each
#: retry is a fresh cache-hot fork; the budget caps cost when the model
#: persistently fails to summarize.
MAX_COMPACT_ATTEMPTS = 3


def _next_compact_attempt(compact_attempt: int) -> int | None:
    """Return the next attempt number, or *None* when the budget is spent.

    Pure helper (no side effects) so the retry budget stays unit-testable
    without a DB.
    """
    try:
        attempt = int(compact_attempt or 0)
    except (TypeError, ValueError):
        attempt = 0
    nxt = attempt + 1
    return nxt if nxt < MAX_COMPACT_ATTEMPTS else None


def _extract_summary_text(message: Message | None) -> str:
    """Extract the compaction summary from a child's final result message."""
    if message is None:
        return ""
    summary_text = ""
    for part in message.parts.all():
        if part.type == MessagePartType.MESSAGE:
            content = part.content.get() if part.content else None
            summary_text += str(content) if content else ""
        elif (
            part.type == MessagePartType.TOOLCALL
            and part.tool_call
            and part.tool_call.task_definition.name == "final_result"
        ):
            try:
                args = part.tool_call.carguments_json or {}
            except Exception:
                args = {}
            summary_text += str(args.get("content", ""))
    return summary_text


def _build_compaction_message(
    _session: Session,
    newest_compacted: Message | None,
    summary_text: str,
    response: Any = None,
) -> Message:
    """Create the COMPACTION boundary message after ``newest_compacted``.

    The message linked list stays a single linear chain: nothing is repointed,
    detached, or orphaned.  ``build_llm_context`` walks backward from the
    newest message and stops at the first message with a COMPACTION part, so
    the compacted range is excluded from the LLM context.  The UI (which walks
    the same ``prev_message`` chain without stopping) can still render the full
    history in order.
    """
    sv = _session.get_version_model()
    current_tail = _session.get_last_message()

    if newest_compacted is None:
        # Nothing to compact — create a trivial summary appended to the
        # current tail so the linked list stays a single chain.
        compaction_message = Message.objects.create(
            session=sv.session,
            session_version=sv,
            response=response,
            role=MessageRole.USER,
            prev_message=current_tail,
        )
        compaction_message.add_part(
            type=MessagePartType.COMPACTION,
            content_type=MessageContentType.TEXT,
            content="Old messages before this summary have been compacted to save context tokens. Summary :",
        )
        compaction_message.add_part(
            type=MessagePartType.COMPACTION,
            content_type=MessageContentType.TEXT,
            content=summary_text,
        )
    else:
        # The first message that followed the compacted range (if any).
        # Captured *before* creating the compaction message so
        # ``newest_compacted``'s ``next_messages`` does not yet include it
        # (otherwise a fully-compacted chain would repoint the compaction
        # message at itself).
        successor = newest_compacted.next_messages.order_by("pk").first()

        compaction_message = Message.objects.create(
            session=sv.session,
            session_version=sv,
            response=response,
            role=MessageRole.USER,
            prev_message=newest_compacted,
        )

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        working_dir = _session.workspace.path if _session.workspace else "unknown"
        compaction_message.add_part(
            type=MessagePartType.COMPACTION,
            content_type=MessageContentType.TEXT,
            content=f"It is now {now}, your working dir is '{working_dir}'.\n",
        )
        compaction_message.add_part(
            type=MessagePartType.COMPACTION,
            content_type=MessageContentType.TEXT,
            content="Old messages before this summary have been compacted to save context tokens. Summary:\n",
        )
        compaction_message.add_part(
            type=MessagePartType.COMPACTION,
            content_type=MessageContentType.TEXT,
            content=summary_text,
        )

        # Relink the first message that followed the compacted range (if any) so
        # it now points back at the compaction message.  Without this the
        # predecessor (newest_compacted) would have two ``next_messages``
        # children and the chain would fork.
        if successor:
            successor.prev_message = compaction_message
            successor.save()

    from runtime.events import publish_model_event

    publish_model_event(compaction_message, "create")
    return compaction_message


def ingest_compaction(
    _session: Session,
    child_session_pk: int | None = None,
    boundary_pk: int | None = None,
    result: Message | None = None,
    compact_attempt: int = 0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Insert the COMPACTION boundary marker and return the marker message.

    Fork flow (auto-compaction via a ``SUBTASK_FORK`` child):
        ``compact_if_needed`` dispatches this task with ``result`` referencing
        the child's ingest call — the framework waits for the child and
        passes its final message in here.  Also provided are ``child_session_pk``
        and ``boundary_pk`` (the newest message to compact).  The summary from
        the child's final message is inserted as the marker after the boundary.

    Legacy flow (``compact_turn`` chain): ``response``/``parts`` come from
    ``parse_llm_response`` and the compacted range is derived from the query
    leftovers.  Kept for the ``/compact`` command and backward compatibility.
    """
    summary_text = ""
    from server.models.sessions.session import SessionModel

    child_session_model = SessionModel.objects.get(pk=child_session_pk)
    child_session = Session(session_model=child_session_model)

    child_session.set_is_active(False)

    if result is None:            
        result = child_session.get_last_message()

    summary_text = _extract_summary_text(result)

    if not summary_text.strip():
        # Never insert an empty marker: it would hide the compacted range
        # behind no summary (silent context loss).  The usual cause is a
        # fork that never produced final_result — e.g. killed by the
        # tool_call_allowlist after going off-task.
        #
        # Retry IMMEDIATELY with a fresh fork instead of hoping for the
        # parent's next over-limit turn: at this point the parent is already
        # at/over its context budget, so its next LLM call may itself
        # overflow before any future compaction runs.  The re-dispatched
        # compact_turn is async (no blocking wait); under the queue strategy
        # it runs right after this call ends.
        nxt = _next_compact_attempt(compact_attempt)
        if nxt is not None:
            retry_call = _session.get_task("compact_turn").delay(
                message=None, compact_attempt=nxt
            )
            return dict(
                compaction_retried=True,
                compact_attempt=nxt,
                child_session_pk=child_session_pk,
                boundary_pk=boundary_pk,
                retry_call=retry_call,
            )
        raise ValueError(
            "Compaction fork produced no summary "
            f"(child_session_pk={child_session_pk}) after "
            f"{MAX_COMPACT_ATTEMPTS} attempts; refusing to insert an "
            "empty COMPACTION marker."
        )

    boundary = Message.objects.get(pk=boundary_pk) if boundary_pk else None

    marker = _build_compaction_message( _session, newest_compacted=boundary, summary_text=summary_text)
         
    return dict(message=marker, **kwargs)
