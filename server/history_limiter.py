from __future__ import annotations

import json
import math
from typing import Any

import tiktoken

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message


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

    return math.ceil(len(json.dumps(message_dict)) / 3.8)


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


def find_compaction_boundary(session: Session, last_message: Message | None) -> Message | None:
    """Find the newest message to compact in a session's chain, query-free.

    Replicates the split logic in ``build_llm_compact_context`` without
    creating a ``Query``:

    - ``compact_size_limit`` (percentage, 0–100, default 15) is the portion of
      tokens to **keep** in full.
    - Walks the ``prev_message`` chain from ``last_message`` backwards, stops
      at the first message with a ``COMPACTION`` part (boundary marker),
      respects ``max_history_messages + 1``.
    - Accumulates ``estimate_message_tokens`` from the **newest** end until the
      keep budget is reached.  The kept messages are the recent tail kept in
      full; the remaining (older) messages are the compacted range.
    - Edge case: if the newest compacted message is an ``ASSISTANT`` message
      with toolcalls (toolcalls require a companion response later), it is
      kept too so the conversation is never split mid-tool-call.

    Returns the newest message that should be compacted — everything older is
    summarized, everything newer is kept.  Returns ``None`` when the whole
    conversation fits within the keep budget (nothing to compact).
    """
    pct = session.compact_size_limit
    if pct <= 0:
        pct = 15

    max_history = session.max_history_messages
    walk_limit = max_history + 1 if max_history is not None else None

    # Walk the chain from the newest message backwards.
    entries: list[Message] = []
    current = last_message
    while current is not None and (walk_limit is None or len(entries) < walk_limit):
        if not current.hide_from_context:
            entries.append(current)
            if current.parts.filter(type=MessagePartType.COMPACTION).exists():
                break
        current = current.prev_message
    if not entries:
        return None

    # entries is newest -> oldest.
    total_tokens = sum(estimate_message_tokens(m) for m in entries)
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

    # The newest compacted message is compacted[0] (entries newest->oldest).
    newest_compacted = compacted[0]

    # Toolcall guard: never split a tool-call turn.  If the newest compacted
    # is an assistant toolcall message, keep it too (move the boundary older).
    if (
        newest_compacted.role == MessageRole.ASSISTANT
        and newest_compacted.parts.filter(type=MessagePartType.TOOLCALL).exists()
    ):
        compacted = compacted[1:]
        if not compacted:
            return None
        newest_compacted = compacted[0]

    return newest_compacted

