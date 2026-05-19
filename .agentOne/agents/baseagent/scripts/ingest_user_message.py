"""
Entry point for user messages into the agent loop.
Normalizes raw input into a Message model, then chains into process_turn.
"""

from runtime.agents.session import Session
from server.models.content import GenericContent
from server.models.message import Message, MessagePart
from server.models.enums.message_enums import MessageContentType


def ingest_user_message(session: Session, message: str, parts) -> Message:
    """
    Normalize user input, persist as a Message, and start the agent loop.

    Called via session.ingest_user_message.delay(message=..., parts=...)
    from the framework when the user sends a chat message.

    Args:
        session:  The active agent session.
        message:  Raw text input (used when parts is None).
        parts:    List of dicts with "content" and "type" keys.

    Returns:
        An AgentTaskCall for process_turn — the framework resolves this
        through the chain until decide_next_step returns the final Message.
    """
    if parts is None and message is not None:
        parts = [{"content": message, "type": "TEXT"}]
    if not parts:
        raise Exception("No message or message parts provided")

    session.reset_unattended_turn_count()
    session_version = session.get_version_model()
    prev_message = session_version.related_messages.filter(next_messages=None).last()

    message = Message.objects.create(
        role="user",
        session_version=session_version,
        prev_message=prev_message,
    )
    for part in parts:
        MessagePart.objects.create(
            content=GenericContent.from_text(part["content"]),
            content_type=MessageContentType.TEXT,
            message=message,
        )

    return session.process_turn.delay(message=message)
