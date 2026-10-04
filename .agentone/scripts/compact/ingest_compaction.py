from __future__ import annotations

from datetime import datetime
from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message
from server.models.queries.response import Response


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
    response: Response | None = None,
    parts = [],
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

    parent_sv = _session.get_version_model()

    if not summary_text.strip():
        # Failure toast anchored at the current tail; the chain is untouched.
        info_message = Message.objects.create(
            role=MessageRole.INFO,
            session=parent_sv.session,
            session_version=parent_sv,
            prev_message=_session.get_last_message(),
        )

        info_message.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content=f"Compaction failed, {compact_attempt+1} of {MAX_COMPACT_ATTEMPTS} attempts",
        )
        try:
            from runtime.events import publish_model_event

            publish_model_event(info_message, "create")
        except Exception:
            pass

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
            # Todo-style retry: dispatch the fresh fork, then resolve the slim
            # ``ingest_compaction_response`` task over its call — the same
            # action/response split as ``todolist_action`` /
            # ``todolist_action_response``.  Returning the wrapper call lets
            # the framework await the retry and resume downstream with the
            # wrapper's properly-shaped result (response/parts/message).
            # Returning the raw retry call (or a dict containing it) would
            # trip the single-ref continuation repoint with a dict that
            # cannot carry the parent turn's response/parts, breaking the
            # resumed decide_next_step with missing arguments.
            retry_call = _session.get_task("compact_turn").delay(
                message=kwargs.get("message"),
                response=response,
                parts=parts,
                compact_attempt=nxt,
            )
            return _session.get_task("ingest_compaction_response").delay(
                compaction_result=retry_call,
                response=response,
                parts=parts,
                message=kwargs.get("message"),
                # The wrapper's dict replaces the parent step's result after
                # the continuation-repoint flattening, so the parent turn's
                # message and outcome flags must travel explicitly — the
                # compact chain's own response/parts are empty (None) and
                # its kwargs never carried the flags
                parent_message=kwargs.get("message"),
                has_final_result=kwargs.get("has_final_result"),
                tool_allowlist_violated=kwargs.get("tool_allowlist_violated"),
                has_tool_calls=kwargs.get("has_tool_calls"),
                has_message=kwargs.get("has_message"),
                compact_attempt=nxt,
            )
        raise ValueError(
            "Compaction fork produced no summary "
            f"(child_session_pk={child_session_pk}) after "
            f"{MAX_COMPACT_ATTEMPTS} attempts; refusing to insert an "
            "empty COMPACTION marker."
        )
    boundary = Message.objects.get(pk=boundary_pk) if boundary_pk else None

    marker = _build_compaction_message( _session, newest_compacted=boundary, summary_text=summary_text)

    # Success toast anchored at the then-current tail — the marker itself when
    # everything was compacted — so the chain keeps exactly one tip.
    info_message = Message.objects.create(
        role=MessageRole.INFO,
        session=parent_sv.session,
        session_version=parent_sv,
        prev_message=_session.get_last_message(),
    )
    info_message.add_part(
        type=MessagePartType.MESSAGE,
        content_type=MessageContentType.TEXT,
        content="Compaction successful",
    )

    try:
        from runtime.events import publish_model_event

        publish_model_event(info_message, "create")
    except Exception:
        pass

    return dict(
        response=response,
        parts=parts,
        message=marker,
        **kwargs,
    )


def ingest_compaction_response(
    _session: Session,
    compaction_result: Any = None,
    response: Any = None,
    parts: list[dict[str, Any]] | None = None,
    message: Message | None = None,
    parent_message: Message | None = None,
    compact_attempt: int = 0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Slim resolver for a retried compaction fork (mirrors todolist_action_response).

    ``compaction_result`` arrives auto-resolved to the retry ``compact_turn``
    chain's final result — the success-shaped ``dict(response, parts,
    message=marker, ...)`` its ``ingest_compaction`` returned.  This wrapper
    re-emits exactly that shape (marker message swapped in, parent turn's
    response/parts preserved) so the waiting ``process_turn`` chain resumes
    ``decide_next_step`` with all required arguments.  The wrapper's own
    result is ref-free, so no further continuation repointing applies.

    ``parent_message`` is the parent turn's assistant message (the compact
    chain's ``message``, carried through untouched): after the repoint
    flattening this dict *is* ``decide_next_step``'s kwargs, so the parent
    message must be present for the ``parts``-fallback there.  Outcome flags
    (``has_final_result``, ``tool_allowlist_violated``) arrive via ``kwargs``
    and are re-emitted the same way.
    """
    marker = message
    if isinstance(compaction_result, dict):
        marker = compaction_result.get("message", marker)
    elif isinstance(compaction_result, Message):
        marker = compaction_result
    if isinstance(marker, dict) and marker.get("_type") == "Message" and "pk" in marker:
        try:
            marker = Message.objects.get(pk=marker["pk"])
        except Message.DoesNotExist:
            marker = message
    return dict(
        response=response,
        parts=parts,
        message=marker,
        parent_message=parent_message,
        compaction_retried=True,
        compact_attempt=compact_attempt,
        **kwargs,
    )
