from __future__ import annotations

from django.db import models


class MessageRole(models.TextChoices):
    """Roles a message participant can have."""

    ASSISTANT = "assistant"
    USER = "user"
    SYSTEM = "system"
    TOOL = "tool"
    DEVELOPER = "developer"
    INFO = "info"


class MessageSource(models.TextChoices):
    """Origin of a message within the system."""

    default = "default"
    human_chat_message = "human_chat_message"
    tool_response = "tool_response"
    assistant_llm_response = "llm_response"
    assistant_code_response = "assistant_code_response"


class MessageContentType(models.TextChoices):
    """Type of content carried by a message or message part."""

    IMAGE = "IMAGE"
    TEXT = "TEXT"
    JSON = "JSON"
    TEMPLATE = "TEMPLATE"


class MessagePartType(models.TextChoices):
    """Structural type of a message part."""

    REASONING = "REASONING"
    MESSAGE = "MESSAGE"
    TOOLCALL = "TOOLCALL"
    COMPACTION = "COMPACTION"
