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
                {% if pyview.subject.health_label %}<span class="key-badge key-missing" title="{{ pyview.subject.status_reason }}">{{ pyview.subject.health_label }}</span>{% endif %}
            </div>

            <div class="rp-section-title">Facts</div>
            <div class="rp-kv"><span>Rank</span><span>{{ pyview.group_rank }}</span></div>
            <div class="rp-kv"><span>Params</span><span>{{ pyview.group_params }}</span></div>
            <div class="rp-kv"><span>Context</span><span>{{ pyview.group_context }}</span></div>
            {% if pyview.subject.status != "UNKNOWN" %}
            <div class="rp-kv"><span>Health</span><span>{{ pyview.subject.health_label or pyview.subject.status }}</span></div>
            {% if pyview.subject.status_reason %}<div class="rp-kv"><span>Reason</span><span>{{ pyview.subject.status_reason }}</span></div>{% endif %}
            {% if pyview.subject.status_retry_at %}<div class="rp-kv"><span>Retry after</span><span>{{ pyview.subject.status_retry_at }}</span></div>{% endif %}
            {% endif %}
            {% if pyview.subject.canonical_id %}
            <div class="rp-kv"><span>Canonical ID</span><span>{{ pyview.subject.canonical_id }}</span></div>
            {% endif %}
            {% if pyview.subject.open_weights %}<div class="rp-kv"><span>Weights</span><span>open</span></div>{% endif %}
            <div class="rp-kv"><span>Last used</span><span>{{ pyview.last_usage }}</span></div>
            {% if pyview.subject.description %}<div class="rp-desc">{{ pyview.subject.description }}</div>{% endif %}

            <div class="rp-section-title">Providers ({{ pyview.provider_rows|length }})</div>
            {% for row in pyview.provider_rows %}
            <div class="rp-link" onclick="pyview.open_provider({{ row.provider_id }})">
                <strong>{{ row.provider }}</strong>
                <span class="muted">{{ row.provider_model_id }}</span>
                <span class="muted">{{ row.key_note }}</span>
                {% if row.health %}<span class="key-badge key-missing" title="{{ row.health_reason }}">{{ row.health }}</span>{% endif %}
                <button class="provider-test-btn" onclick="event.stopPropagation(); pyview.test_model({{ row.provider_id }})" title="Test this provider's model">Test</button>
                {% if row.conditions %}<span class="rp-conditions">{{ row.conditions }}</span>{% endif %}
            </div>
            {% endfor %}
            {% if pyview._probe %}
            <div style="margin-top:8px;font-size:12px">
                {% if pyview._probe.verdict == "running" %}
                <span class="muted">⟳ testing {{ pyview._probe.model }}…</span>
                <script>setTimeout(function(){ pyview._poll_probe(); }, 2500);</script>
                {% elif pyview._probe.verdict == "healthy" %}
                <span style="color:var(--success)">✓ {{ pyview._probe.model }} · {{ pyview._probe.latency_ms }}ms · {{ pyview._probe.tokens.prompt + pyview._probe.tokens.completion }} tok</span>
                {% if pyview._probe.session_pk %}<button class="provider-card-btn provider-card-btn-ghost" style="font-size:10px;padding:2px 6px;margin-left:6px" onclick="pyview.open_test_session({{ pyview._probe.session_pk }})">open</button>{% endif %}
                {% elif pyview._probe.verdict == "no_tool_call" %}
                <span style="color:#b7791f">⚠ {{ pyview._probe.model }} replied but no final_result · {{ pyview._probe.latency_ms }}ms</span>
                {% if pyview._probe.session_pk %}<button class="provider-card-btn provider-card-btn-ghost" style="font-size:10px;padding:2px 6px;margin-left:6px" onclick="pyview.open_test_session({{ pyview._probe.session_pk }})">open</button>{% endif %}
                {% elif pyview._probe.verdict == "failed" %}
                <span style="color:var(--error)">✗ {{ pyview._probe.error_kind or 'failed' }}: {{ pyview._probe.error_message }}</span>
                {% endif %}
            </div>
            {% endif %}
        </div>
        <div class="resize-handle" id="rightpanelResize"></div>
    '''

    def __init__(self, subject: AiModel, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._probe: dict | None = None
        self._probe_model_pk: int | None = None

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

    def test_model(self, provider_id: int) -> None:
        """Smoke-test the member model for *provider_id*."""
        from server.models.providers.ai_model import AiModel
        from server.tasks.probe_model import probe_model
        model = None
        for member in self._members:
            if member.api_provider_id == provider_id:
                model = member
                break
        if model is None:
            model = AiModel.objects.filter(pk=provider_id).first()
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

