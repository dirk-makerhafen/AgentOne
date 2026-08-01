from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.message import Message
from server.models.queries.response import Response


def ingest_compaction(
    _session: Session, response: Response, parts: list[dict[str, Any]]
) -> dict[str, Any]:
    summary_text = ""
    for part in parts:
        if part["type"] == "message":
            content = part["content"]
            summary_text = str(content) if content else ""

    # The remaining QueryMessages (kept messages were deleted by
    # build_llm_compact_context) are exactly the messages that were
    # compacted — no need to recalculate the split.
    # Deduplicate by source_message and sort by PK so the range
    # boundaries are correct even when a source_message has multiple
    # QueryMessages (e.g. content + toolcall parts).
    seen: set[int] = set()
    compacted_messages: list[Message] = []
    for qm in response.query.related_query_messages.all():
        msg = qm.source_message
        if msg and msg.pk not in seen:
            seen.add(msg.pk)
            compacted_messages.append(msg)

    compacted_messages.sort(key=lambda m: m.pk)

    if not compacted_messages:
        # Nothing to compact — create a trivial summary appended to the
        # current tail so the linked list stays a single chain.
        sv = _session.get_version_model()
        current_tail = Message.objects.filter(
            session_version=sv, next_messages=None,
        ).order_by("-pk").first()
        compaction_message = Message.objects.create(
            session_version=sv,
            response=response,
            role="user",
            prev_message=current_tail,
        )
        compaction_message.add_part(
            type="COMPACTION", content_type="text", content="Old messages before this summary have been compacted to save context tokens. Summary:"
        )
        compaction_message.add_part(
            type="COMPACTION", content_type="text", content=summary_text
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

    compaction_message = Message.objects.create(
        session_version=_session.get_version_model(),
        response=response,
        role="user",
        prev_message=newest_compacted,
    )
    compaction_message.add_part(
        type="COMPACTION", content_type="text", content="Old messages before this summary have been compacted to save context tokens. Summary:"
    )
    compaction_message.add_part(
        type="COMPACTION",
        content_type="text",
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
