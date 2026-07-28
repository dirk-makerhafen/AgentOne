
from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel


def list_subsessions(_session: Session) -> dict[str, Any]:
    """List all subsessions you have created.

    Returns metadata for every child session, active or inactive.
    Does **not** contain message content — use ``await_subsession`` to
    retrieve a specific subsession's latest reply.

    Args:
        (none besides _session, which is bound automatically).

    Returns:
        ``{"subsessions": [{
            "session_pk": int,
            "session_name": str,
            "description": str,
            "agent": str,
            "status": "active" | "idle",
            "turn_count": int,
            "created_at": str (ISO 8601)
        }, ...]}``
    """
    children = SessionModel.objects.filter(
        parent_session=_session.model,
    ).order_by("-created_at").select_related("latest_session_version__agent")

    subsessions: list[dict[str, Any]] = []
    for child in children:
        lsv = child.latest_session_version
        av = lsv.agent if lsv else None
        subsessions.append({
            "session_pk": child.pk,
            "session_name": child.name,
            "description": lsv.description if lsv else "",
            "agent": av.name if av else "?",
            "status": "active" if child.is_active else "idle",
            "turn_count": child.turn_count,
            "created_at": child.created_at.isoformat() if child.created_at else "",
        })

    return {"subsessions": subsessions}
