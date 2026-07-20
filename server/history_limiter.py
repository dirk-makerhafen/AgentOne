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





class HistoryLimiter:
    def __init__(self, session: Session, all_entries: list[Message]):
        self.session = session
        self.all_entries = all_entries

    def is_tool_call_limited(self, tool_call, message) -> bool:
        return False

    def is_general_message_limited(self, rule_name: str, entry) -> bool:
        return False
