"""
List child sessions of the current session with metadata.

Returns name, status (active/idle), turn count, and creation time for
each child session.  Does NOT return subagent output — use await_subagents
for that.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel


def list_subagents(session: Session) -> dict[str, Any]:
    """
    List child sessions spawned by the current session.

    Args:
        session: The calling agent's session (bound automatically).

    Returns:
        A dict with key ``subagents`` — a list of per-session metadata:
        ``{session_pk, name, status, turn_count, created_at}``.
        *status* is ``"active"`` when ``is_active`` is ``True``,
        otherwise ``"idle"``.
    """
    children = SessionModel.objects.filter(
        parent_session=session.model,
    ).order_by("-created_at").select_related("latest_session_version__agent")

    subagents: list[dict[str, Any]] = []
    for child in children:
        av = child.latest_session_version.agent if child.latest_session_version else None
        subagents.append({
            "session_pk": child.pk,
            "name": av.name if av else "?",
            "status": "active" if child.is_active else "idle",
            "turn_count": child.turn_count,
            "created_at": child.created_at.isoformat() if child.created_at else "",
        })

    return {"subagents": subagents}
