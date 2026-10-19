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


class MessageType(models.TextChoices):
    """Semantic classification of a whole message (independent of its role).

    ``role`` is the LLM-facing wire role (user / assistant / system / tool);
    ``message_type`` describes what the message *is* in the conversation.  The
    two coexist: a compaction marker is ``role=user, message_type=compaction``.
    """

    DEFAULT = "default"
    USER_CHAT = "user_chat"
    ASSISTANT_MESSAGE = "assistant_message"
    TOOL_RESPONSE = "tool_response"
    SYSTEM_NOTICE = "system_notice"
    COMPACTION = "compaction"
    REFLECTION = "reflection"
    INFO = "info"
    BOOTSTRAP = "bootstrap"


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
