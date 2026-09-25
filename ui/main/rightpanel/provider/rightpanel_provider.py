"""Provider detail for the right panel — opened from the insight providers table."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.db.models import Count, Sum
from django.utils import timezone

from server.models.providers.api_provider import ApiProvider
from server.models.queries.response import Response, ResponseStatus
from ui.lib.model_view import ModelView
from ui.main.insights.providers import _human, LIMIT_LABELS

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel


class RightPanelProvider(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="rp-detail">
            <div class="rp-detail-title">{{ pyview.subject.name }}</div>
            <div class="rp-detail-sub muted">{{ pyview.subject.url }}</div>
            <div class="rp-badges">
                {% if pyview.subject.is_local %}<span class="mode-badge">local</span>{% endif %}
                {% if pyview.subject.data.get("default_api_key") %}<span class="key-badge key-builtin">built-in key</span>{% endif %}
                {% if not pyview.subject.enabled %}<span class="key-badge key-missing">disabled</span>{% endif %}
            </div>

            <div class="rp-section-title">About</div>
            <div class="rp-desc">{{ pyview.full_description }}</div>

            <div class="rp-section-title">Routing</div>
            <div class="rp-kv"><span>Endpoint</span><span>{{ pyview.subject.url or "—" }}</span></div>
            <div class="rp-kv"><span>Protocol</span><span>{{ pyview.subject.litellm_prefix or "OpenAI-compatible" }}</span></div>
            <div class="rp-kv"><span>Slug</span><span>{{ pyview.subject.slug }}</span></div>
            {% if pyview.subject.data.get("api_key_url") %}
            <div class="rp-kv"><span>Get key</span><span><a href="{{ pyview.subject.data.get('api_key_url') }}" target="_blank">console</a></span></div>
            {% endif %}

            <div class="rp-section-title">API keys ({{ pyview.key_rows|length }})</div>
            {% for key in pyview.key_rows %}
            <div class="rp-kv"><span>{{ key.comment or "key" }}</span><span>{% if key.enabled %}✓{% else %}off{% endif %}{% if key.cooling %} · cooling down{% endif %}</span></div>
            {% endfor %}
            {% if not pyview.key_rows %}<div class="muted">No keys configured.</div>{% endif %}

            <div class="rp-section-title">Limits</div>
            {% for label, value in pyview.limit_rows %}
            <div class="rp-kv"><span>{{ label }}</span><span>{{ value }}</span></div>
            {% endfor %}
            {% if not pyview.limit_rows %}<div class="muted">Unlimited.</div>{% endif %}

            <div class="rp-section-title">Usage</div>
            {% for window, stats in pyview.usage_rows %}
            <div class="rp-kv"><span>{{ window }}</span><span>{{ stats }}</span></div>
            {% endfor %}

            <div class="rp-section-title">Models ({{ pyview.model_rows|length }})</div>
            {% for model in pyview.model_rows %}
            <div class="rp-link" onclick="pyview.open_model({{ model.id }})">
                <strong>{{ model.name }}</strong>
                <span class="muted">{{ model.provider_model_id }}</span>
            </div>
            {% endfor %}
        </div>
        <div class="resize-handle" id="rightpanelResize"></div>
    '''

    def __init__(self, subject: ApiProvider, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    def open_model(self, model_id: int) -> None:
        from server.models.providers.ai_model import AiModel
        from ui.main.rightpanel.model.rightpanel_model import RightPanelModel
        model = AiModel.objects.filter(pk=model_id).first()
        if model is not None:
            self.parent.parent.rightpanel.set_view(RightPanelModel, model)

    @property
    def full_description(self) -> str:
        """Full provider blurb: research-doc description, else the setup
        instructions, else the endpoint URL (never raises)."""
        try:
            info = getattr(self.subject, "data", None) or {}
            desc = (info.get("description") or "").strip()
            if desc:
                return desc
            setup = (info.get("setup_instructions") or "").strip()
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
                "comment": key.comment,
                "enabled": key.enabled,
                "cooling": bool(key.rate_limit_until and key.rate_limit_until > now),
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
    def model_rows(self) -> list:
        return list(
            self.subject.aimodels.all().order_by("name").values("id", "name", "provider_model_id")
        )
