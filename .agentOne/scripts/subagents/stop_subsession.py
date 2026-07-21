
from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel


def stop_subsession(session: Session, sessionname: str) -> dict[str, Any]:
    """Stop a running subsession by name.

    The subsession is marked inactive — it will no longer process messages.
    The session record is preserved but no new turns will be dispatched.

    Args:
        sessionname: Name of the subsession to stop. Must exist and be active.

    Returns:
        On success: ``{"result": "Subsession '<name>' ended"}``.
        On error: ``{"error": "No active subsession '<name>' found"}``.
    """
    updated = SessionModel.objects.filter(
        parent_session=session.model,
        name=sessionname,
        is_active=True,
    ).update(is_active=False)

    if updated:
        return {"result": f"Subsession '{sessionname}' ended"}
    return {"error": f"No active subsession '{sessionname}' found"}
