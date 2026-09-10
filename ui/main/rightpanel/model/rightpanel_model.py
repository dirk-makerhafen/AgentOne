"""Model detail for the right panel — opened from insight tables.

The subject is one representative ``AiModel`` row; the view groups all rows
sharing its canonical identity (``canonical_id`` → ``leaderboard_id`` →
``name``) across providers.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.models.providers.ai_model import AiModel
from ui.lib.model_view import ModelView
from ui.main.insights.models import MODE_LABELS, _params_str, _rank_str

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel


class RightPanelModel(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="rp-detail">
            <div class="rp-detail-title">{{ pyview.group_name }}</div>
            {% if pyview.group_developer %}<div class="rp-detail-sub muted">{{ pyview.group_developer }}</div>{% endif %}
            <div class="rp-badges">
                {% for mode in pyview.group_modes %}<span class="mode-badge">{{ mode }}</span>{% endfor %}
                {% if not pyview.subject.enabled %}<span class="key-badge key-missing">disabled</span>{% endif %}
            </div>

            <div class="rp-section-title">Facts</div>
            <div class="rp-kv"><span>Rank</span><span>{{ pyview.group_rank }}</span></div>
            <div class="rp-kv"><span>Params</span><span>{{ pyview.group_params }}</span></div>
            <div class="rp-kv"><span>Context</span><span>{{ pyview.group_context }}</span></div>
            {% if pyview.subject.canonical_id %}
            <div class="rp-kv"><span>Canonical ID</span><span>{{ pyview.subject.canonical_id }}</span></div>
            {% endif %}
            {% if pyview.subject.open_weights %}<div class="rp-kv"><span>Weights</span><span>open</span></div>{% endif %}
            {% if pyview.subject.description %}<div class="rp-desc">{{ pyview.subject.description }}</div>{% endif %}

            <div class="rp-section-title">Providers ({{ pyview.provider_rows|length }})</div>
            {% for row in pyview.provider_rows %}
            <div class="rp-link" onclick="pyview.open_provider({{ row.provider_id }})">
                <strong>{{ row.provider }}</strong>
                <span class="muted">{{ row.provider_model_id }}</span>
                <span class="muted">{{ row.key_note }}</span>
                {% if row.conditions %}<span class="rp-conditions">{{ row.conditions }}</span>{% endif %}
            </div>
            {% endfor %}
        </div>
        <div class="resize-handle" id="rightpanelResize"></div>
    '''

    def __init__(self, subject: AiModel, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    def open_provider(self, provider_id: int) -> None:
        from server.models.providers.api_provider import ApiProvider
        from ui.main.rightpanel.provider.rightpanel_provider import RightPanelProvider
        provider = ApiProvider.objects.filter(pk=provider_id).first()
        if provider is not None:
            self.parent.parent.rightpanel.set_view(RightPanelProvider, provider)

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
    def provider_rows(self) -> list[dict]:
        rows = []
        for member in self._members:
            provider = member.api_provider
            has_key = bool(provider.data.get("default_api_key")) or any(
                k.enabled for k in provider.api_keys.all()
            )
            rows.append({
                "provider_id": provider.pk,
                "provider": provider.name,
                "provider_model_id": member.provider_model_id,
                "key_note": "✓ key" if has_key else "no key",
                "conditions": (member.data.get("conditions") or ""),
            })
        rows.sort(key=lambda r: r["provider"].lower())
        return rows
