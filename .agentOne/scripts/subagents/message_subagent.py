"""
Send a follow-up message to a running subagent session (non-blocking).

The message is added as a new user message in the child session's
conversation. The subagent's agent loop will process it on the next tick.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel


def message_subagent(session: Session, session_pk: int, query: str) -> dict[str, Any]:
    """
    Send a follow-up message to a previously spawned subagent.

    The message is appended to the child session's conversation history.
    The subagent processes it asynchronously.

    Args:
        session: The calling agent's session (bound automatically).
        session_pk: The pk of the child session to message.
        query: The follow-up message content.

    Returns:
        A dict with result or error.
    """
    try:
        child_model = SessionModel.objects.get(pk=session_pk)
    except SessionModel.DoesNotExist:
        return {"error": f"Session {session_pk} not found"}

    child_session = Session(session_model=child_model)

    parts = [{"type": "message", "content_type": "text", "content": query}]
    child_session.add_user_message(parts=parts)

    return {"result": "sent", "session_pk": session_pk}
