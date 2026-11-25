"""Mutable current routing binding for a session.

The immutable :class:`~server.models.settings.SettingsModel` records the
*intent* (what model/provider/key the session is pinned to and how much
failover is allowed).  This row records the *resolved* binding the router is
currently using.  Keeping it separate is deliberate: a provider failover, a
key rotation or a model downgrade updates one mutable row instead of minting a
new ``SessionVersionModel`` on every retry.
"""
from __future__ import annotations

from django.db import models

from server.models.base_model import BaseModel


class SessionRoute(BaseModel):
    """The offering/key a session is currently bound to (mutable state)."""

    session = models.OneToOneField(
        "server.SessionModel",
        on_delete=models.CASCADE,
        related_name="route",
    )
    offering = models.ForeignKey(
        "server.AiModelOffering",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="+",
    )
    api_key = models.ForeignKey(
        "server.ApiKey",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="+",
    )

    #: When the current binding was chosen.
    resolved_at = models.DateTimeField(default=None, null=True, blank=True)
    #: How many times the binding has moved since the session was created.
    switch_count = models.IntegerField(default=0)
    #: Timestamp + short machine-readable reason of the last move.
    last_switch_at = models.DateTimeField(default=None, null=True, blank=True)
    last_reason = models.CharField(max_length=512, default="", blank=True)
    #: Last few attempt outcomes, newest last.  Small JSON list so the UI can
    #: explain "tried A (429), B (503), served by C".
    attempts: models.JSONField = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "session route"
        verbose_name_plural = "session routes"

    def __str__(self) -> str:
        offering = self.offering
        return f"SessionRoute:{self.session_id}->{offering}" if offering else f"SessionRoute:{self.session_id}"

    def record_attempt(self, label: str, reason: str, *, ok: bool = False, limit: int = 8) -> None:
        """Append one attempt outcome (bounded list)."""
        entry = {"label": str(label)[:200], "reason": str(reason)[:300], "ok": bool(ok)}
        attempts = list(self.attempts or [])
        attempts.append(entry)
        self.attempts = attempts[-limit:]
