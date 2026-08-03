"""
Entry point for user messages into the agent loop.
Normalizes raw input into a Message model, then chains into process_turn.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessageRole
from server.models.message import Message


def ingest_user_message(_session: Session, parts: list[dict[str, Any]]) -> Message:
    """
    Normalize user input, persist as a Message, and start the agent loop.

    Called via _session.ingest_user_message.delay(message=..., parts=...)
    from the framework when the user sends a chat message.

    Args:
        _session: The active agent session.
        parts:  List of dicts with 
                type:
                    Part type key (``"message"``, ``"reasoning"``, ``"toolcall"``).
                content_type:
                    Content type enum value (text, image, template, json).
                content:
                    Raw content value or a :class:`GenericContent` instance.  When
                    ``content_type`` is ``IMAGE``, TEXT or JSON and ``content`` is not
                    already a :class:`GenericContent`, one is created automatically.
                template_data:
                    Optional template data (string or :class:`GenericContent`).  Used when ``content_type`` is ``TEMPLATE``.
    Returns:
        An AgentTaskCall for process_turn -- the framework resolves this
        through the chain until decide_next_step returns the final Message.
    """

    _session.reset_unattended_turn_count()
    _session.reset_turn_count()
    session_version = _session.get_version_model()
    prev_message = _session.get_messages().filter(next_messages=None).last()

    message = Message.objects.create(
        role=MessageRole.USER,
        session=session_version.session,
        session_version=session_version,
        prev_message=prev_message,
    )

    for part in parts:
        message.add_part(
            type=part["type"],
            content_type=part["content_type"],
            content=part["content"],
            template_data=part.get("template_data", None),
            tool_call=part.get("tool_call", None),
        )

    from runtime.events import publish_model_event
    publish_model_event(message, "create")

    return _session.get_task("process_turn").delay(message=message)
