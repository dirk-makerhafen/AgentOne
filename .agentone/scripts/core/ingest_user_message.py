"""
Entry point for user messages into the agent loop.
Normalizes the flexible message spec into Message models, then (optionally)
chains into process_turn.
"""

from __future__ import annotations

from typing import Any

from runtime.session.messages import normalize_messages
from runtime.session.session import Session
from server.models.message import Message


def ingest_user_message(_session: Session, message: Any = None, execute_turn: bool = True) -> Any:
    """
    Normalize *message*, persist the resulting Message(s), and start the agent loop.

    The spec supports a bare string, a list of strings / part dicts (one user
    message with many parts) or a list of message dicts (mixed roles) -- see
    :func:`runtime.session.messages.normalize_messages`.

    When ``execute_turn`` is True the last message starts a ``process_turn``
    chain (the framework resolves that call through the chain until
    ``decide_next_step`` returns the final Message).  When False the messages
    are only persisted -- the caller may chain a turn itself -- and the last
    created Message is returned.

    Args:
        _session: The active agent session.
        message: The message spec (string, part dict(s) or message dict(s)).
        execute_turn: Whether to start a turn for the last message.
    """
    messages = normalize_messages(message)

    session_version = _session.get_version_model()
    prev_message = _session.get_last_message()
    created: Message | None = None

    from runtime.events import publish_model_event

    for spec in messages:
        created = Message.objects.create(
            role=spec["role"],
            session=session_version.session,
            session_version=session_version,
            prev_message=prev_message,
        )
        for part in spec["parts"]:
            created.add_part(
                type=part["part_type"],
                content_type=part["content_type"],
                content=part["content"],
                template_data=part.get("template_data", None),
                tool_call=part.get("tool_call", None),
            )
        publish_model_event(created, "create")
        prev_message = created

    if not execute_turn:
        return created

    _session.reset_unattended_turn_count()
    _session.reset_turn_count()
    return _session.get_task("process_turn").delay(message=created)
