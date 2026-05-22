"""
Entry point for user messages into the agent loop.
Normalizes raw input into a Message model, then chains into process_turn.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.message import Message


def ingest_user_message(session: Session, parts: list[dict[str, Any]]) -> Message:
    """
    Normalize user input, persist as a Message, and start the agent loop.

    Called via session.ingest_user_message.delay(message=..., parts=...)
    from the framework when the user sends a chat message.

    Args:
        session: The active agent session.
        parts:   List of dicts with "content" and "type" keys. Each Part
                 may also contain optional keys: template_data, tool_call.

    Returns:
        An AgentTaskCall for process_turn -- the framework resolves this
        through the chain until decide_next_step returns the final Message.
    """

    session.reset_unattended_turn_count()
    session_version = session.get_version_model()
    prev_message = session.get_messages().filter(next_messages=None).last()

    message = Message.objects.create(
        role="user",
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

    return session.get_task("process_turn").delay(message=message)
