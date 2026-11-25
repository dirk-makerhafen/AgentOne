"""Mutable session route state (the current offering/key binding)."""
from __future__ import annotations

from typing import Any

from django.utils import timezone

MAX_ATTEMPTS = 8


def get_route(session: Any):
    """Return the session's :class:`SessionRoute` row, or ``None``."""
    from server.models.sessions.session_route import SessionRoute

    session_model = getattr(session, "model", None)
    pk = getattr(session_model, "pk", None)
    if pk is None:
        return None
    return (
        SessionRoute.objects.select_related("offering__api_provider", "offering__model", "api_key")
        .filter(session_id=pk)
        .first()
    )


def set_route(
    session: Any,
    offering: Any,
    api_key: Any = None,
    *,
    reason: str = "",
    attempts: list[dict[str, Any]] | None = None,
) -> Any:
    """Bind the session to *offering* / *api_key* without minting a version."""
    from server.models.sessions.session_route import SessionRoute

    session_model = getattr(session, "model", None)
    pk = getattr(session_model, "pk", None)
    if pk is None:
        return None
    now = timezone.now()
    row = SessionRoute.objects.filter(session_id=pk).first()
    if row is None:
        row = SessionRoute(
            session_id=pk,
            offering=offering,
            api_key=api_key,
            resolved_at=now,
            last_reason=(reason or "")[:512],
            attempts=(attempts or [])[-MAX_ATTEMPTS:],
        )
        row.save()
        return row

    changed = row.offering_id != getattr(offering, "pk", None) or row.api_key_id != getattr(
        api_key, "pk", None
    )
    row.offering = offering
    row.api_key = api_key
    row.resolved_at = now
    if changed:
        row.switch_count = (row.switch_count or 0) + 1
        row.last_switch_at = now
        row.last_reason = (reason or "")[:512]
    if attempts is not None:
        row.attempts = list(attempts)[-MAX_ATTEMPTS:]
    row.save()
    return row


def record_attempt(session: Any, label: str, reason: str, *, ok: bool = False) -> None:
    """Append one attempt outcome to the route trace (best-effort)."""
    row = get_route(session)
    if row is None:
        return
    row.record_attempt(label, reason, ok=ok)
    row.save()


def clear_route(session: Any) -> None:
    """Forget the current binding (next resolution starts from the intent)."""
    from server.models.sessions.session_route import SessionRoute

    pk = getattr(getattr(session, "model", None), "pk", None)
    if pk is None:
        return
    SessionRoute.objects.filter(session_id=pk).update(
        offering=None, api_key=None, resolved_at=None
    )
