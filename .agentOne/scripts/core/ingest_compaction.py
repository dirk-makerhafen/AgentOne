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

    # The compaction replaces everything from oldest_compacted (chronologically
    # first) through newest_compacted (chronologically last).
    oldest_compacted = compacted_messages[0]
    newest_compacted = compacted_messages[-1]
    prev_for_compaction = oldest_compacted.prev_message

    # The first message that follows the compacted range (if any).
    first_kept = newest_compacted.next_messages.filter(
        hide_from_context=False,
    ).order_by("pk").first()

    compaction_message = Message.objects.create(
        session_version=_session.get_version_model(),
        response=response,
        role="user",
        prev_message=prev_for_compaction,
    )
    compaction_message.add_part(
        type="COMPACTION", content_type="text", content="Old messages before this summary have been compacted to save context tokens. Summary:"
    )
    compaction_message.add_part(
        type="COMPACTION",
        content_type="text",
        content=summary_text,
    )

    if first_kept:
        first_kept.prev_message = compaction_message
        first_kept.save()
    else:
        # Everything was compacted — relink the trigger message directly.
        response.query.trigger_message.prev_message = compaction_message
        response.query.trigger_message.save()

    # Detach the old branch from the chain so the message linked list
    # remains a single chain (no fork).  Without this, the predecessor
    # of *oldest_compacted* has two ``next_messages`` children, and
    # ``filter(next_messages=None).last()`` may pick the wrong tail
    # (the old branch instead of the active one).
    if oldest_compacted.prev_message_id:
        oldest_compacted.prev_message = None
        oldest_compacted.save()

    # Repointing the kept message at the compaction message orphans the whole
    # compacted range plus any of its hidden children.  Every message no
    # longer reachable from the compaction message (backward via prev_message,
    # forward via next_messages) shows up as a dangling tail in
    # ``filter(next_messages=None)`` (I7 fork).  Self-reference them all
    # (I8 pattern) so the tail query only ever returns the active tail.
    session_messages = list(Message.objects.filter(
        session_version=_session.get_version_model(),
    ).only("pk", "prev_message_id"))
    prev_map = {m.pk: m.prev_message_id for m in session_messages}

    # Forward walk: everything that follows the compaction message.
    active: set[int] = set()
    stack = [compaction_message.pk]
    while stack:
        mid = stack.pop()
        if mid in active:
            continue
        active.add(mid)
        for child_id, parent_id in prev_map.items():
            if parent_id == mid:
                stack.append(child_id)

    # Backward walk: everything that precedes it on the active chain.
    cur: int | None = compaction_message.prev_message_id
    while cur is not None and cur not in active and cur in prev_map:
        active.add(cur)
        cur = prev_map[cur]

    for m in session_messages:
        if m.pk not in active and m.pk != m.prev_message_id:
            m.prev_message_id = m.pk
            m.save()

    from runtime.events import publish_model_event
    publish_model_event(compaction_message, "create")

    return dict(
        response=response,
        parts=parts,
        message=compaction_message,
    )
