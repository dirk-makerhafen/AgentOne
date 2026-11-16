"""Model detail data helpers.

Computes grouped/canonical model detail data (facts, providers, usage). The Django/htmx web UI
renders model details via ``webui.views.insights.model_detail`` +
``webui/templates/webui/insights/_model_detail.html``.

The subject is one representative ``AiModel`` row; the view groups all rows sharing its
canonical identity (``canonical_id`` → ``leaderboard_id`` → ``name``) across providers.
"""
from __future__ import annotations

from server.models.providers.ai_model import AiModel
from webui.features.insights.models import MODE_LABELS, _params_str, _rank_str


class RightPanelModel:
    """Model detail data (no UI rendering)."""

    def __init__(self, subject: AiModel | None = None, *args, **kwargs):
        self._subject_ref = subject

    @property
    def subject(self):
        return getattr(self, "_subject_ref", None)

    @property
    def _group_key(self) -> str:
        subject = self.subject
        return subject.canonical_id or subject.leaderboard_id or subject.name

    @property
    def _members(self):
        key = self._group_key
        subject = self.subject
        base = AiModel.objects.select_related("api_provider").prefetch_related("api_provider__api_keys")
        if subject.canonical_id:
            return list(base.filter(canonical_id=key))
        if subject.leaderboard_id:
            return list(base.filter(leaderboard_id=key))
        return list(base.filter(name=key))

    @property
    def group_name(self) -> str:
        return self.subject.name

    @property
    def group_developer(self) -> str:
        return self.subject.developer

    @property
    def group_modes(self) -> list[str]:
        return [label for field, label in MODE_LABELS
                if any(getattr(m, field, False) for m in self._members)]

    @property
    def group_rank(self) -> str:
        ranks = [(m.leaderboard_rank, m.leaderboard_rank_is_estimate) for m in self._members
                 if m.leaderboard_rank is not None]
        if not ranks:
            return "—"
        return _rank_str(*min(ranks))

    @property
    def group_params(self) -> str:
        total = max((m.total_parameters or 0) for m in self._members)
        return _params_str(total or None)

    @property
    def group_context(self) -> str:
        ctx = max((m.context_length or 0) for m in self._members)
        if not ctx:
            return "—"
        if ctx >= 1_000_000:
            return f"{ctx / 1_000_000:g}M"
        return f"{ctx / 1_000:g}k"

    @property
    def last_usage(self) -> str:
        # Get the most recent last_usage from all members
        last = None
        for member in self._members:
            if member.last_usage and (last is None or member.last_usage > last):
                last = member.last_usage
        if last:
            return last.strftime("%Y-%m-%d %H:%M:%S")
        return "—"

    @property
    def provider_rows(self) -> list[dict]:
        rows = []
        for member in self._members:
            provider = member.api_provider
            has_key = bool(provider.default_api_key) or any(
                k.enabled for k in provider.api_keys.all()
            )
            rows.append({
                "provider_id": provider.pk,
                "provider": provider.name,
                "provider_model_id": member.provider_model_id,
                "key_note": "✓ key" if has_key else "no key",
                "health": member.health_label,
                "health_reason": member.status_reason,
                "conditions": member.conditions,
            })
        rows.sort(key=lambda r: r["provider"].lower())
        return rows

