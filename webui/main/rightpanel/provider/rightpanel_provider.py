"""Provider detail for the right panel — opened from the insight providers table."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.db.models import Count, Sum
from django.utils import timezone

from server.models.providers.api_provider import ApiProvider
from server.models.queries.response import Response, ResponseStatus
from webui.main.insights.providers import _human, LIMIT_LABELS

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel


class RightPanelProvider:
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"

    @property
    def subject(self):
        return getattr(self, "_subject_ref", None)
    TEMPLATE_STR = '''
        <div class="rp-detail">
            <div class="rp-detail-title">{{ pyview.subject.name }}</div>
            <div class="rp-detail-sub muted">{{ pyview.subject.url }}</div>
            <div class="rp-badges">
                {% if pyview.subject.is_local %}<span class="mode-badge">local</span>{% endif %}
                {% if pyview.subject.default_api_key %}<span class="key-badge key-builtin">built-in key</span>{% endif %}
                {% if not pyview.subject.enabled %}<span class="key-badge key-missing">disabled</span>{% endif %}
                {% if pyview.subject.health_label %}<span class="key-badge key-missing" title="{{ pyview.subject.status_reason }}">{{ pyview.subject.health_label }}</span>{% endif %}
            </div>

            <div class="rp-section-title">About</div>
            <div class="rp-desc">{{ pyview.full_description }}</div>

            <div class="rp-section-title">Routing</div>
            <div class="rp-kv"><span>Endpoint</span><span>{{ pyview.subject.url or "—" }}</span></div>
            <div class="rp-kv"><span>Protocol</span><span>{{ pyview.subject.litellm_prefix or "OpenAI-compatible" }}</span></div>
            <div class="rp-kv"><span>Slug</span><span>{{ pyview.subject.slug }}</span></div>
            {% if pyview.subject.api_key_url %}
            <div class="rp-kv"><span>Get key</span><span><a href="{{ pyview.subject.api_key_url }}" target="_blank">console</a></span></div>
            {% endif %}

            <div class="rp-section-title">API keys ({{ pyview.key_rows|length }})</div>
            {% for key in pyview.key_rows %}
            <div class="rp-kv"><span>{{ key.comment or "key" }}</span><span>{% if key.enabled %}✓{% else %}off{% endif %}{% if key.cooling %} · cooling down{% endif %}{% if key.health and key.status != "RATE_LIMITED" %} · {{ key.health }}{% endif %}</span></div>
            {% endfor %}
            {% if not pyview.key_rows %}<div class="muted">No keys configured.</div>{% endif %}

            <div class="rp-section-title">Health</div>
            <div class="rp-kv"><span>Status</span><span>{{ pyview.subject.health_label or pyview.subject.status|lower }}</span></div>
            {% if pyview.subject.status_reason %}<div class="rp-kv"><span>Reason</span><span>{{ pyview.subject.status_reason }}</span></div>{% endif %}
            {% if pyview.subject.status_retry_at %}<div class="rp-kv"><span>Retry after</span><span>{{ pyview.subject.status_retry_at }}</span></div>{% endif %}
            {% if pyview.subject.consecutive_failures %}<div class="rp-kv"><span>Failures</span><span>{{ pyview.subject.consecutive_failures }}</span></div>{% endif %}

            <div class="rp-section-title">Limits</div>
            {% for label, value in pyview.limit_rows %}
            <div class="rp-kv"><span>{{ label }}</span><span>{{ value }}</span></div>
            {% endfor %}
            {% if not pyview.limit_rows %}<div class="muted">Unlimited.</div>{% endif %}

            <div class="rp-section-title">Usage</div>
            <div class="rp-kv"><span>Last used</span><span>{{ pyview.last_usage }}</span></div>
            {% for window, stats in pyview.usage_rows %}
            <div class="rp-kv"><span>{{ window }}</span><span>{{ stats }}</span></div>
            {% endfor %}

            <div class="rp-section-title">Models ({{ pyview.model_rows|length }})</div>
            {% for model in pyview.model_rows %}
            <div class="rp-link" onclick="pyview.open_model({{ model.id }})">
                <strong>{{ model.name }}</strong>
                <span class="muted">{{ model.provider_model_id }}</span>
                <button class="provider-test-btn" onclick="event.stopPropagation(); pyview.test_model({{ model.id }})" title="Test this model">Test</button>
            </div>
            {% endfor %}

            <div class="rp-actions">
                {% if pyview._probe and pyview._probe.verdict == "running" %}
                <div class="muted" style="font-size:12px;margin-bottom:6px">⟳ testing {{ pyview._probe.model }}…</div>
                <script>setTimeout(function(){ pyview._poll_probe(); }, 2500);</script>
                {% elif pyview._probe and pyview._probe.verdict == "healthy" %}
                <div style="font-size:12px;margin-bottom:6px;color:var(--success)">✓ {{ pyview._probe.model }} · {{ pyview._probe.latency_ms }}ms · {{ pyview._probe.tokens.prompt + pyview._probe.tokens.completion }} tok</div>
                {% if pyview._probe.session_pk %}<button class="provider-card-btn provider-card-btn-ghost" onclick="pyview.open_test_session({{ pyview._probe.session_pk }})">Open session</button>{% endif %}
                {% elif pyview._probe and pyview._probe.verdict == "no_tool_call" %}
                <div style="font-size:12px;margin-bottom:6px;color:#b7791f">⚠ {{ pyview._probe.model }} replied but did not call final_result · {{ pyview._probe.latency_ms }}ms</div>
                {% if pyview._probe.session_pk %}<button class="provider-card-btn provider-card-btn-ghost" onclick="pyview.open_test_session({{ pyview._probe.session_pk }})">Open session</button>{% endif %}
                {% elif pyview._probe and pyview._probe.verdict == "failed" %}
                <div style="font-size:12px;margin-bottom:6px;color:var(--error)">✗ {{ pyview._probe.error_kind or 'failed' }}: {{ pyview._probe.error_message }}</div>
                {% endif %}
                <button class="provider-card-btn provider-card-btn-primary" onclick="pyview.test_provider()" {% if pyview._probe and pyview._probe.verdict == "running" %}disabled{% endif %}>Test provider</button>
            </div>
        </div>
        <div class="resize-handle" id="rightpanelResize"></div>
    '''

    def open_model(self, model_id: int) -> None:
        from server.models.providers.ai_model import AiModel
        from webui.main.rightpanel.model.rightpanel_model import RightPanelModel
        model = AiModel.objects.filter(pk=model_id).first()
        if model is not None:
            self.parent.parent.rightpanel.set_view(RightPanelModel, model)

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
            return self.subject.last_usage.strftime("%Y-%m-%d %H:%M:%S")
        return "—"

    @property
    def model_rows(self) -> list:
        return list(
            self.subject.aimodels.all().order_by("name").values("id", "name", "provider_model_id")
        )



    def open_test_session(self, session_pk: int) -> None:
        try:
            from server.models.sessions.session import SessionModel
            from ui.main.chat.chat import Chat
            sm = SessionModel.objects.filter(pk=int(session_pk)).first()
            if sm is None:
                return
            cur = self
            seen = set()
            main_view = None
            while cur is not None and id(cur) not in seen:
                seen.add(id(cur))
                if hasattr(cur, "create_and_open_tab"):
                    main_view = cur
                    break
                cur = getattr(cur, "parent", None)
            if main_view is not None:
                main_view.create_and_open_tab(Chat, sm)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _resolve_session(self):
        queue = [self]
        seen = set()
        while queue:
            obj = queue.pop(0)
            if obj is None or id(obj) in seen:
                continue
            seen.add(id(obj))
            for attr in ("session", "current_session"):
                try:
                    val = getattr(obj, attr, None)
                except Exception:  # pylint: disable=broad-exception-caught
                    val = None
                if val is not None:
                    return val
            for child_attr in ("selected_tab_view", "main_panel", "rightpanel"):
                child = getattr(obj, child_attr, None)
                if child is not None and id(child) not in seen:
                    queue.append(child)
            parent = getattr(obj, "parent", None)
            if parent is not None and id(parent) not in seen:
                queue.append(parent)
        return None

    def __init__(self, subject: ApiProvider, parent, **kwargs):
        self._probe: dict | None = None
        self._probe_model_pk: int | None = None

    def test_provider(self) -> None:
        """Smoke-test the provider via its best usable model."""
        from runtime.test_run import best_usable_model
        from server.tasks.probe_model import probe_model
        model = best_usable_model(self.subject.pk)
        if model is None:
            self._probe = {"verdict": "failed", "error_message": "No usable enabled model"}
            self.update()
            return
        self._probe = {"verdict": "running", "model": model.name, "model_pk": model.pk}
        self._probe_model_pk = model.pk
        self.update()
        try:
            from ui.lib.model_view import orm_subscribe
            orm_subscribe(self, f"AiModel.pk:{model.pk}", self._on_probe_event)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            probe_model.delay(model.pk)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._probe = {"verdict": "failed", "error_message": str(exc)}
            self.update()

    def test_model(self, model_id: int) -> None:
        """Smoke-test a specific model."""
        from server.models.providers.ai_model import AiModel
        from server.tasks.probe_model import probe_model
        model = AiModel.objects.filter(pk=model_id).first()
        if model is None:
            return
        self._probe = {"verdict": "running", "model": model.name, "model_pk": model.pk}
        self._probe_model_pk = model.pk
        self.update()
        try:
            from ui.lib.model_view import orm_subscribe
            orm_subscribe(self, f"AiModel.pk:{model.pk}", self._on_probe_event)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            probe_model.delay(model.pk)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._probe = {"verdict": "failed", "error_message": str(exc)}
            self.update()

    def _on_probe_event(self, key=None, model=None, pk=None, action=None, data=None, **_kw):
        try:
            payload = None
            if isinstance(data, dict) and "probe" in data:
                payload = data["probe"]
            if payload is None:
                from server.tasks.probe_model import get_cached_result
                payload = get_cached_result(int(pk)) if pk is not None else None
            if payload is not None:
                self._probe = payload
                self.update()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _poll_probe(self) -> None:
        if self._probe_model_pk is None:
            return
        try:
            from server.tasks.probe_model import get_cached_result
            cached = get_cached_result(self._probe_model_pk)
            if cached is not None:
                self._probe = cached
                self.update()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

