from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message
from server.models.queries.response import Response


def ingest_compaction(
    _session: Session, response: Response, parts: list[dict[str, Any]]
) -> dict[str, Any]:
    summary_text = ""
    for part in parts:
        if part["type"] == MessagePartType.MESSAGE:
            content = part["content"]
            summary_text = str(content) if content else ""

    # The remaining QueryMessages (kept messages were deleted by
    # build_llm_compact_context) are exactly the messages that were
    # compacted — no need to recalculate the split.
    # Deduplicate by source_message.  Multiple QueryMessages for the same
    # source_message (e.g. content + toolcall parts) are adjacent, so the
    # first occurrence preserves the order.
    seen: set[int] = set()
    compacted_messages: list[Message] = []
    for qm in response.query.related_query_messages.all():
        msg = qm.source_message
        if msg and msg.pk not in seen:
            seen.add(msg.pk)
            compacted_messages.append(msg)

    # Order the compacted messages by their position in the ``prev_message``
    # chain, NOT by pk: a COMPACTION marker inserted mid-chain was created
    # *after* the messages that follow it in the chain, so it has a higher pk
    # yet sits *before* them.  Sorting by pk would pick the marker as the
    # "newest" compacted message and place the boundary too early, leaving
    # messages that were meant to be compacted in the context.  Walk the
    # linked list to recover the true chain order.
    if len(compacted_messages) > 1:
        by_id = {m.pk: m for m in compacted_messages}
        followers = {
            m.prev_message_id: m
            for m in compacted_messages
            if m.prev_message_id in by_id
        }
        head = next(
            (m for m in compacted_messages if m.prev_message_id not in by_id),
            compacted_messages[0],
        )
        ordered: list[Message] = []
        current: Message | None = head
        while current is not None:
            ordered.append(current)
            current = followers.get(current.pk)
        compacted_messages = ordered

    if not compacted_messages:
        # Nothing to compact — create a trivial summary appended to the
        # current tail so the linked list stays a single chain.
        sv = _session.get_version_model()
        current_tail = Message.objects.filter(session_version=sv, next_messages=None).order_by("-pk").first()
        compaction_message = Message.objects.create(session=sv.session, session_version=sv, response=response, role=MessageRole.USER, prev_message=current_tail,)
        compaction_message.add_part(
            type=MessagePartType.COMPACTION, content_type=MessageContentType.TEXT, content="Old messages before this summary have been compacted to save context tokens. Summary :"
        )
        compaction_message.add_part(
            type=MessagePartType.COMPACTION, content_type=MessageContentType.TEXT, content=summary_text
        )
        from runtime.events import publish_model_event
        publish_model_event(compaction_message, "create")
        return dict(response=response, parts=parts, message=compaction_message)

    # The compaction is inserted as a boundary marker immediately after the
    # newest compacted message (chronologically last).  The message linked
    # list stays a single linear chain: nothing is repointed, detached, or
    # orphaned.
    #
    # ``build_llm_context`` walks backward from the newest message and stops
    # at the first message with a COMPACTION part, so the compacted range is
    # excluded from the LLM context.  The UI (which walks the same
    # ``prev_message`` chain without stopping) can still render the full
    # history in order.
    newest_compacted = compacted_messages[-1]

    # The first message that followed the compacted range (if any).  Captured
    # *before* creating the compaction message so ``newest_compacted``'s
    # ``next_messages`` does not yet include it (otherwise a fully-compacted
    # chain would repoint the compaction message at itself).
    successor = newest_compacted.next_messages.order_by("pk").first()

    sv = _session.get_version_model()
    compaction_message = Message.objects.create(
        session=sv.session,
        session_version=sv,
        response=response,
        role=MessageRole.USER,
        prev_message=newest_compacted,
    )
    compaction_message.add_part(
        type=MessagePartType.COMPACTION, 
        content_type=MessageContentType.TEXT, 
        content="Old messages before this summary have been compacted to save context tokens. Summary:"
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

    return dict(
        response=response,
        parts=parts,
        message=compaction_message,
    )
