"""
Send a ``lint`` command to a running brain session.

The brain will health-check its vault and optionally run the archiving pass.
Use ``await_subagents`` to wait for the result.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel


def brain_lint(session: Session, brain_name: str | None = None, message: str | None = None) -> dict[str, Any]:
    """
    Send a ``lint`` command to a brain subagent session.

    Args:
        session: The calling agent's session (bound automatically).
        brain_name: Optional brain session name. Auto-resolves if exactly one
                    brain subagent exists; errors if multiple are found.
        message: Optional focus instruction — narrows the lint to a specific
                 concern (e.g. "check only orphaned entity pages", "find stale
                 index.md links").

    Returns:
        A dict indicating the command was sent.
    """
    child_session, error = _resolve_brain(session, brain_name)
    if error:
        return {"error": error}

    query = f"lint — {message}" if message else "lint"
    parts = [{"type": "message", "content_type": "text", "content": query}]
    child_session.add_user_message(parts=parts)

    return {"result": "sent", "session_pk": child_session.model.pk, "command": "lint", "focus": message}


def _resolve_brain(session: Session, brain_name: str | None = None):
    """Find a brain subagent session by name, or auto-resolve if exactly one exists."""
    subagent_version = session.get_subagent("brain")
    if not subagent_version:
        return None, "Brain agent not found"

    agent_version = subagent_version.get_version_model()

    if brain_name:
        children = SessionModel.objects.filter(
            parent_session=session.model,
            name=brain_name,
            latest_session_version__agent=agent_version,
        )
        if not children.exists():
            return None, f"Brain session '{brain_name}' not found"
        child = children.first()
    else:
        children = SessionModel.objects.filter(
            parent_session=session.model,
            latest_session_version__agent=agent_version,
        ).order_by("-created_at")

        count = children.count()
        if count == 0:
            return None, "No brain session found. Call brain_init first or provide brain_name."
        if count > 1:
            names = [c.name for c in children]
            return None, f"Multiple brain sessions found. Provide brain_name: {names}"

        child = children.first()

    return Session(session_model=child), None
