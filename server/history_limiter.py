from __future__ import annotations

import json
from typing import Any

import tiktoken

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message
from server.models.queries.query_message_part import estimate_openai_tokens


_ENCODER_CACHE: dict[str, tiktoken.Encoding] = {}


def _get_encoder() -> tiktoken.Encoding:
    name = "cl100k_base"
    if name not in _ENCODER_CACHE:
        _ENCODER_CACHE[name] = tiktoken.get_encoding(name)
    return _ENCODER_CACHE[name]


def estimate_message_tokens(message: Message) -> int:
    """Estimate the token count of a single :class:`Message`.

    Mirrors the heuristic used by ``QueryMessage.to_openai_message``:
    ``ceil(len(json.dumps(openai_message)) / 3.8)``, so the query-free
    compaction boundary stays consistent with the token counts stored on
    QueryMessages.
    """
    if message is None:
        return 0
    content_parts: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    reasoning_parts: list[str] = []
    for part in message.parts.all():
        if part.type == MessagePartType.TOOLCALL:
            tc = part.tool_call
            if tc:
                tool_calls.append(
                    {
                        "type": "function",
                        "id": f"tc-{tc.pk}",
                        "function": {
                            "name": tc.task_definition.name,
                            "arguments": json.dumps(tc.carguments_json),
                        },
                    }
                )
            continue
        if part.type == MessagePartType.REASONING:
            if part.content:
                reasoning_parts.append(str(part.content.get()))
            continue
        if part.content_type == MessageContentType.TEXT:
            content_parts.append({"type": "text", "text": str(part.content.get() if part.content else "")})
        elif part.content_type == MessageContentType.TEMPLATE:
            rendered = part.to_string()
            content_parts.append({"type": "text", "text": str(rendered) if rendered is not None else ""})
        elif part.content_type == MessageContentType.JSON:
            content_parts.append({"type": "text", "text": json.dumps(part.content.get() if part.content else "")})
        elif part.content_type == MessageContentType.IMAGE:
            content_parts.append({"type": "image_url", "image_url": {"url": str(part.content.get() if part.content else "")}})

    merged = _merge_text_parts(content_parts)
    message_dict: dict[str, Any] = {"role": message.role, "content": merged}
    if tool_calls:
        message_dict["tool_calls"] = tool_calls
    if message.role == MessageRole.ASSISTANT and reasoning_parts:
        message_dict["reasoning_content"] = "".join(reasoning_parts)

    return estimate_openai_tokens(message_dict)


def _merge_text_parts(parts: list[dict[str, Any]]) -> str | list[dict[str, Any]]:
    """Merge adjacent text parts, prepend prefix, append postfix.

    Mirrors ``QueryMessage._merge_text_parts`` so estimates match the real
    openai payload the LLM would see.
    """
    if not parts:
        return ""
    merged = [parts[0]]
    for part in parts[1:]:
        if merged[-1]["type"] == part["type"] == "text":
            merged[-1]["text"] += part["text"]
        else:
            merged.append(part)
    if len(merged) == 1 and merged[0]["type"] == "text":
        return merged[0]["text"]
    return merged


def walk_compaction_entries(session: Session, last_message: Message | None) -> list[Message]:
    """Walk the ``prev_message`` chain newest-first for compaction math.

    Skips ``INFO``/hidden messages, stops at the first ``COMPACTION`` part
    (boundary marker) and respects ``max_history_messages + 1`` — mirroring
    ``build_llm_context``.  Shared by the boundary finder and the token
    estimate so both agree on the walked range.
    """
    max_history = session.max_history_messages
    walk_limit = max_history + 1 if max_history is not None else None

    entries: list[Message] = []
    current = last_message
    while current is not None and (walk_limit is None or len(entries) < walk_limit):
        if not current.hide_from_context and current.role != MessageRole.INFO:
            entries.append(current)
            if current.parts.filter(type=MessagePartType.COMPACTION).exists():
                break
        current = current.prev_message
    return entries


def estimate_entries_tokens(entries: list[Message]) -> int:
    """Sum :func:`estimate_message_tokens` over walked entries."""
    return sum(estimate_message_tokens(m) for m in entries)


def last_activity_at(session: Session) -> Any | None:
    """Return the newest message timestamp of the session, or *None* if empty."""
    latest = (
        Message.objects.filter(session_id=session.model.pk)
        .order_by("-created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    return latest


def idle_seconds(session: Session) -> float | None:
    """Return seconds since the session's newest message, or *None* if empty."""
    from django.utils import timezone

    latest = last_activity_at(session)
    if latest is None:
        return None
    return (timezone.now() - latest).total_seconds()


def find_compaction_boundary(session: Session, last_message: Message | None) -> Message | None:
    """Find the newest message to compact in a session's chain, query-free.

    Replicates the split logic in ``build_llm_compact_context`` without
    creating a ``Query``:

    - ``auto_compact_keep_percent`` (percentage, 0–100) is the portion of
      newest tokens to **keep** in full. Unset (``None``) means the default
      15; an explicit ``0`` keeps nothing — everything is compacted.
    - Walks the ``prev_message`` chain from ``last_message`` backwards, stops
      at the first message with a ``COMPACTION`` part (boundary marker),
      respects ``max_history_messages + 1``.
    - Accumulates ``estimate_message_tokens`` from the **newest** end until the
      keep budget is reached.  The kept messages are the recent tail kept in
      full; the remaining (older) messages are the compacted range.
    - Edge case: if the newest compacted message is an ``ASSISTANT`` message
      with toolcalls (toolcalls require a companion response later), it is
      kept too so the conversation is never split mid-tool-call.  This also
      protects an approval-halted tail under keep-percent 0: the undecided
      toolcall stays live, everything before it is summarized.

    Returns the newest message that should be compacted — everything older is
    summarized, everything newer is kept.  Returns ``None`` when the whole
    conversation fits within the keep budget (nothing to compact).
    """
    pct = session.auto_compact_keep_percent
    if pct is None:
        pct = 15

    # entries is newest -> oldest.
    entries = walk_compaction_entries(session, last_message)
    if not entries:
        return None

    total_tokens = estimate_entries_tokens(entries)
    if pct <= 0:
        # Explicit zero: keep nothing, compact the whole walked range.
        compacted = list(entries)
    else:
        keep_tokens = max(1, int(total_tokens * pct / 100))

        kept_token_count = 0
        kept_messages: list[Message] = []
        for msg in entries:
            kept_token_count += estimate_message_tokens(msg)
            kept_messages.append(msg)
            if kept_token_count >= keep_tokens:
                break

        kept_ids = {m.pk for m in kept_messages}
        compacted = [m for m in entries if m.pk not in kept_ids]
    if not compacted:
        return None

    # Toolcall guard: never split a tool-call turn.  If the newest compacted
    # message is an assistant toolcall message, keep it too (move the
    # boundary older) — its response arrives after it, so only the last such
    # message must stay live; older toolcalls (with their responses compacted
    # alongside them, or dangling with no response possible anymore) are safe
    # to summarize.  This also protects an approval-halted tail under
    # keep-percent 0: the undecided toolcall stays live, everything before it
    # is summarized.
    if (
        compacted
        and compacted[0].role == MessageRole.ASSISTANT
        and compacted[0].parts.filter(type=MessagePartType.TOOLCALL).exists()
    ):
        compacted = compacted[1:]
    if not compacted:
        return None
    newest_compacted = compacted[0]

    return newest_compacted

