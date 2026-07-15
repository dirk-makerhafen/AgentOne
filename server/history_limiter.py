from __future__ import annotations

import json
import tiktoken
from typing import Any

from django.db.models import QuerySet

from runtime.session.session import Session
from server.models.message import Message, MessagePart


_ENCODER_CACHE: dict[str, tiktoken.Encoding] = {}


def _get_encoder() -> tiktoken.Encoding:
    name = "cl100k_base"
    if name not in _ENCODER_CACHE:
        _ENCODER_CACHE[name] = tiktoken.get_encoding(name)
    return _ENCODER_CACHE[name]


def estimate_message_tokens(message: Message) -> int:
    """Estimate the token count of a Message by serializing its parts."""
    encoder = _get_encoder()
    total = 0
    for part in message.parts.all():
        text = part.to_string() or ""
        total += len(encoder.encode(text))
    role_overhead = len(encoder.encode(message.role or "user")) + 10
    return total + role_overhead


def estimate_tokens_from_text(text: str) -> int:
    encoder = _get_encoder()
    return len(encoder.encode(text))


def find_compaction_boundary(session: Session, trigger_message_pk: int) -> int:
    """Return the pk of the most recent compaction boundary Message (0 if none)."""
    boundary = Message.objects.filter(
        session_version__session=session.model,
        parts__type="COMPACTION",
        pk__lte=trigger_message_pk,
    ).order_by("-created_at").first()
    return boundary.pk if boundary else 0


class HistoryLimiter:
    def __init__(self, session: Session, all_entries: list[Message]):
        self.session = session
        self.all_entries = all_entries

    def is_tool_call_limited(self, tool_call, message) -> bool:
        return False

    def is_general_message_limited(self, rule_name: str, entry) -> bool:
        return False

    @staticmethod
    def estimate_total_tokens(messages: list[Message]) -> int:
        return sum(estimate_message_tokens(m) for m in messages)

    @staticmethod
    def find_turn_boundary(messages: list[Message], target_tokens: int) -> int:
        """Find the index (newest-first) that best fits within target_tokens,
        rounded to the nearest natural turn boundary (end of an assistant message).

        Args:
            messages: List of Messages ordered newest-first.
            target_tokens: Maximum tokens to keep.

        Returns:
            Index into the reversed (newest-first) list marking the cut point.
            Messages at index < cut_point are compacted; index >= cut_point are kept.
        """
        cumulative = 0
        cut_index = 0
        for i, msg in enumerate(messages):
            tokens = estimate_message_tokens(msg)
            if cumulative + tokens > target_tokens:
                cut_index = i
                break
            cumulative += tokens

        if cut_index == 0:
            return 0

        for i in range(cut_index, len(messages)):
            if messages[i].role == "assistant":
                return i

        return cut_index
