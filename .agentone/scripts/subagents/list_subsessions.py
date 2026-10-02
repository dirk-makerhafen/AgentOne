
from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessageRole
from server.models.message import Message
from server.models.sessions.session import SessionModel

# A subsession that finished stays visible until the calling session has
# advanced a few more user messages ("turns").
RECENT_USER_MESSAGES = 3


def _recent_cutoff(_session: Session):
    """Timestamp of the oldest of the last few user messages in *session*.

    Returns ``None`` when the session has no user messages yet (then only
    active subsessions are shown).
    """
    recent = list(
        Message.objects.filter(
            session_version__session=_session.model,
            role=MessageRole.USER,
        ).order_by("-created_at").values_list("created_at", flat=True)[:RECENT_USER_MESSAGES]
    )
    if not recent:
        return None
    return recent[-1]


def list_subsessions(_session: Session) -> dict[str, Any]:
    """List the subsessions you have created.

    Returns metadata for every **active** child session plus subsessions that
    finished recently.  A finished subsession stays listed until the calling
    session has advanced a few more user messages (``RECENT_USER_MESSAGES``),
    so you can pick up its result for the next few turns.

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
            "last_active_at": str (ISO 8601) or "",
            "created_at": str (ISO 8601)
        }, ...]}``
    """
    cutoff = _recent_cutoff(_session)

    children = SessionModel.objects.filter(
        parent_session=_session.model,
    ).order_by("-created_at").select_related("latest_session_version__agent")

    if cutoff is None:
        children = [c for c in children if c.is_active]
    else:
        children = [
            c for c in children
            if c.is_active or (c.last_active_at and c.last_active_at >= cutoff)
        ]

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
            "last_active_at": child.last_active_at.isoformat() if child.last_active_at else "",
            "created_at": child.created_at.isoformat() if child.created_at else "",
        })

    return {"subsessions": subsessions}
