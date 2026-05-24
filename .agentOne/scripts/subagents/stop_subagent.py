"""
Mark a child subagent session as inactive, preventing further processing.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel


def stop_subagent(session: Session, session_pk: int) -> dict[str, Any]:
    """
    End a subagent session by marking it as inactive.

    Args:
        session: The calling agent's session (bound automatically).
        session_pk: The pk of the child session to stop.

    Returns:
        A dict with result or error.
    """
    updated = SessionModel.objects.filter(pk=session_pk, is_active=True, parent_session=session).update(is_active=False)
    return {"result": f"Session {session_pk} ended"}
