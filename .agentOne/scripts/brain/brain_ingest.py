"""
Send an ``ingest`` command to a running brain session.

The message is appended to the brain's conversation; the brain processes it
asynchronously. Use ``await_subagents`` to wait for completion.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel


def brain_ingest(session: Session, target: str, brain_name: str | None = None) -> dict[str, Any]:
    """
    Send an ``ingest`` command to a brain subagent session.

    Args:
        session: The calling agent's session (bound automatically).
        target: File path or URL to ingest.
        brain_name: Optional brain session name. Auto-resolves if exactly one
                    brain subagent exists; errors if multiple are found.

    Returns:
        A dict indicating the command was sent.
    """
    child_session, error = _resolve_brain(session, brain_name)
    if error:
        return {"error": error}

    parts = [{"type": "message", "content_type": "text", "content": f"ingest {target}"}]
    child_session.add_user_message(parts=parts)

    return {"result": "sent", "session_pk": child_session.model.pk, "command": "ingest", "target": target}


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
