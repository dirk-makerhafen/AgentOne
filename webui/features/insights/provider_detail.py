"""Provider detail data helpers.

Computes provider detail data (keys, limits, usage windows, models). The Django/htmx web UI
renders provider details via ``webui.views.insights.provider_detail`` +
``webui/templates/webui/insights/_provider_detail.html``.
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from server.models.providers.api_provider import ApiProvider
from server.models.queries.response import Response, ResponseStatus
from webui.features.insights.providers import _human, LIMIT_LABELS


class RightPanelProvider:
    """Provider detail data (no UI rendering)."""

    def __init__(self, subject: ApiProvider | None = None, *args, **kwargs):
        self._subject_ref = subject

    @property
    def subject(self):
        return getattr(self, "_subject_ref", None)

    @property
    def full_description(self) -> str:
        """Full provider blurb: research-doc description, else the setup
        instructions, else the endpoint URL (never raises)."""
        try:
            desc = (self.subject.description or "").strip()
            if desc:
                return desc
            setup = (self.subject.setup_instructions or "").strip()
            if setup:
                return setup
            return getattr(self.subject, "url", "") or "—"
        except Exception:
            return "—"

    @property
    def key_rows(self) -> list[dict]:
        now = timezone.now()
        return [
            {
                "id": key.pk,
                "comment": key.comment,
                "enabled": key.enabled,
                "cooling": bool(key.rate_limit_until and key.rate_limit_until > now),
                "status": key.status,
                "health": key.health_label,
            }
            for key in self.subject.api_keys.all().order_by("-enabled", "id")
        ]

    @property
    def limit_rows(self) -> list[tuple[str, int]]:
        return [(label, getattr(self.subject, field, 0))
                for field, label in LIMIT_LABELS
                if getattr(self.subject, field, 0)]

    @property
    def usage_rows(self) -> list[tuple[str, str]]:
        now = timezone.now()
        rows = []
        for label, delta in (("24h", timedelta(hours=24)),
                             ("7d", timedelta(days=7)),
                             ("30d", timedelta(days=30))):
            agg = (
                Response.objects.filter(
                    status=ResponseStatus.SUCCESS,
                    created_at__gte=now - delta,
                    aimodel__api_provider=self.subject,
                )
                .aggregate(req=Count("id"), prompt=Sum("prompt_tokens"), comp=Sum("completion_tokens"))
            )
            tok = (agg["prompt"] or 0) + (agg["comp"] or 0)
            rows.append((label, f"{_human(agg['req'] or 0)} req · {_human(tok)} tok"))
        return rows

    @property
    def last_usage(self) -> str:
        if self.subject.last_usage:
            return timezone.localtime(self.subject.last_usage).strftime("%Y-%m-%d %H:%M:%S")
        return "—"

    @property
    def model_rows(self) -> list:
        return list(
            self.subject.offerings.all().order_by("name").values("id", "name", "provider_model_id")
        )

