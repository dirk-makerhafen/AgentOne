from __future__ import annotations

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType
from server.models.message import Message
from server.models.queries.query import Query
from server.history_limiter import (
    HistoryLimiter,
    find_compaction_boundary,
)
from server.compact import _format_messages_for_compaction, _COMPACTION_SYSTEM_PROMPT


def build_llm_compact_context(session: Session, message: Message) -> Query:
    boundary_pk = find_compaction_boundary(session, message.pk)

    messages = list(Message.objects.filter(
        session_version__session=session.model,
        pk__gte=boundary_pk,
        pk__lte=message.pk,
    ).order_by("-created_at"))

    auto_limit = session.auto_compact_limit
    compact_limit = session.compact_size_limit
    if compact_limit <= 0:
        compact_limit = int(auto_limit * 0.85) if auto_limit > 0 else 130000

    cut_index = HistoryLimiter.find_turn_boundary(messages, compact_limit)
    messages_to_compact = messages[cut_index:]

    existing_summary = ""
    if boundary_pk > 0:
        boundary_msg = Message.objects.get(pk=boundary_pk)
        compact_parts = boundary_msg.parts.filter(type="COMPACTION")
        if compact_parts.exists():
            existing_summary = compact_parts.first().to_string() or ""

    compact_text = _format_messages_for_compaction(messages_to_compact)

    prompt = f"""Current compacted summary:
{existing_summary or "(none)"}

New conversation turns to incorporate:
{compact_text}

Produce a new compacted summary that preserves key context from the existing summary and incorporates relevant new information. Be concise but specific."""

    query = Query.objects.create(
        session_version=session.get_version_model(),
        trigger_message=message,
    )

    if session.system_prompt:
        query.add_message(
            role="system",
            content_type=MessageContentType.TEMPLATE,
            content=session.system_prompt,
            template_data={},
        )

    query.add_message(
        role="system",
        content_type=MessageContentType.TEXT,
        content=_COMPACTION_SYSTEM_PROMPT,
    )

    query.add_message(
        role="user",
        content_type=MessageContentType.TEXT,
        content=prompt,
    )

    return query
