from __future__ import annotations
from typing import TYPE_CHECKING
from django.db.models import Q as _Q
from server.models.providers.api_provider import ApiProvider
from server.models.providers.api_key import ApiKey
from ui.lib.model_view import ModelView, orm_subscribe, orm_unsubscribe_view
from ui.main.insights.providers import _limits_str

if TYPE_CHECKING:
    from ui.main.settings.settings import SettingsView
    from ui.app import UiApp


def sort_provider_rows(rows: list[dict], col: str, desc: bool) -> list[dict]:
    """Sort settings provider row dicts (pure, DB-free).

    ``col`` is one of name/models/limits/key; unknown columns keep the
    input order. Names/limits sort ascending, numbers/keys descending
    unless ``desc`` says otherwise.
    """
    key_order = {"none": 0, "built-in": 1, "keys": 2}

    def sort_key(row: dict):
        if col == "models":
            return row["model_count"]
        if col == "key":
            return (key_order[row["key_state"]], row["key_count"])
        if col == "limits":
            return row["limits"].lower()
        if col == "name":
            return row["name"].lower()
        return 0

    if col not in ("name", "models", "limits", "key"):
        return rows
    return sorted(rows, key=sort_key, reverse=desc)


def _provider_description(provider: ApiProvider) -> str:
    """Short human description for the settings table.

    Prefers the research-doc blurb stored by the provider loader, then the
    first line of the setup instructions, then the endpoint URL.
    """
    desc = (provider.description or "").strip()
    if desc:
        return desc
    setup = (provider.setup_instructions or "").strip()
    if setup:
        first = setup.splitlines()[0].strip()
        # Strip leading list markers ("1. ", "- ") for a cleaner cell.
        import re

        first = re.sub(r"^(\d+[.)]|[-*])\s+", "", first)
        if first:
            return first if len(first) <= 160 else first[:159].rstrip() + "…"
    return provider.url or "—"


class SettingPanelProviders(ModelView):
    """Providers settings as a compact insights-style table.

    One row per enabled provider: name, model count, limits, key state and
    description.  "Add key" / "Edit keys" expands an inline key editor below
    the row (list, enable/disable, delete, add) instead of rendering every
    provider's key form at once.
    """
    DOM_ELEMENT_CLASS = "settings-pane"
    TEMPLATE_STR = '''
        <div class="settings-section-head">
            <div>
                <div class="settings-section-title" data-i18n="providers_section_title">Providers</div>
                <div class="settings-section-meta" data-i18n="providers_section_meta">Manage API keys for AI providers. Changes take effect immediately.</div>
            </div>
        </div>
        {% if pyview.provider_rows %}
        <table class="insights-table settings-providers-table">
            <thead><tr>
                <th class="sortable" onclick="pyview.apply_sort('name')">Provider{{ pyview.sort_arrow('name') }}</th>
                <th class="num sortable" onclick="pyview.apply_sort('models')">Models{{ pyview.sort_arrow('models') }}</th>
                <th class="sortable" onclick="pyview.apply_sort('limits')">Limits{{ pyview.sort_arrow('limits') }}</th>
                <th class="sortable" onclick="pyview.apply_sort('key')">API key{{ pyview.sort_arrow('key') }}</th>
                <th>Description</th>
                <th>Last used</th>
                <th></th>
            </tr></thead>
            <tbody>
            {% for row in pyview.provider_rows %}
            <tr class="clickable{% if row.id == pyview._expanded_id or row.id == pyview._detail_id %} selected{% endif %}" onclick="pyview.open_provider({{ row.id }})">
                <td><strong>{{ row.name }}</strong>{% if row.is_local %} <span class="mode-badge">local</span>{% endif %}</td>
                <td class="num">{{ row.model_count }}</td>
                <td class="muted">{{ row.limits }}</td>
                <td>{% if row.key_state == "built-in" %}<span class="key-badge key-builtin">built-in</span>{% elif row.key_state == "keys" %}<span class="key-badge key-ok">✓ {{ row.key_count }}</span>{% else %}<span class="key-badge key-missing">—</span>{% endif %}</td>
                <td class="muted settings-providers-desc" title="{{ row.description }}">{{ row.description }}</td>
                <td class="muted">{{ row.last_usage }}</td>
                <td class="num settings-providers-actions">
                    {% if row.api_key_url %}
                    <a href="{{ row.api_key_url }}" target="_blank" class="provider-card-btn provider-card-btn-ghost" onclick="event.stopPropagation()" style="text-decoration:none">Get key</a>
                    {% endif %}
                    {% set probe = row.probe %}
                    {% if probe and probe.verdict == "running" %}
                    <span class="provider-card-btn provider-card-btn-ghost" style="font-size:10px;padding:3px 8px">⟳ testing {{ probe.model or "" }}…</span>
                    <script>setTimeout(function(){ pyview._poll_probe({{ row.id }}); }, 2500);</script>
                    {% elif probe and probe.verdict == "healthy" %}
                    <span class="provider-card-btn provider-card-btn-ghost" style="font-size:10px;padding:3px 8px;color:var(--success)" title="{{ probe.answer }} · {{ probe.latency_ms }}ms · {{ probe.tokens.prompt + probe.tokens.completion }} tok{% if probe.session_pk %} · session {{ probe.session_pk }}{% endif %}">✓ {{ probe.model }} · {{ probe.latency_ms }}ms</span>
                    {% if probe.session_pk %}<a href="#" class="provider-card-btn provider-card-btn-ghost" style="font-size:10px;padding:3px 8px" onclick="event.stopPropagation(); pyview.open_test_session({{ probe.session_pk }}); return false;">open</a>{% endif %}
                    {% elif probe and probe.verdict == "no_tool_call" %}
                    <span class="provider-card-btn provider-card-btn-ghost" style="font-size:10px;padding:3px 8px;color:#b7791f" title="{{ probe.answer }}">⚠ no tool call · {{ probe.latency_ms }}ms</span>
                    {% if probe.session_pk %}<a href="#" class="provider-card-btn provider-card-btn-ghost" style="font-size:10px;padding:3px 8px" onclick="event.stopPropagation(); pyview.open_test_session({{ probe.session_pk }}); return false;">open</a>{% endif %}
                    {% elif probe and probe.verdict == "failed" %}
                    <span class="provider-card-btn provider-card-btn-danger" style="font-size:10px;padding:3px 8px" title="{{ probe.error_kind or '' }}: {{ probe.error_message }}">✗ {{ (probe.error_kind or 'failed') }} · retry?</span>
                    {% endif %}
                    <button type="button" class="provider-card-btn provider-card-btn-primary" onclick="event.stopPropagation(); pyview.test_provider({{ row.id }})" title="Test provider"{% if probe and probe.verdict == "running" %} disabled{% endif %}>Test</button>
                    {% if row.key_state == "none" %}
                    <button type="button" class="provider-card-btn provider-card-btn-primary" onclick="event.stopPropagation(); pyview.open_add({{ row.id }})">Add API key</button>
                    {% else %}
                    <button type="button" class="provider-card-btn provider-card-btn-ghost" onclick="event.stopPropagation(); pyview.toggle_expanded({{ row.id }})">{% if row.id == pyview._expanded_id %}Close{% else %}Edit keys{% endif %}</button>
                    {% endif %}
                </td>
            </tr>
            {% if row.id == pyview._expanded_id %}
            <tr class="settings-providers-editor-row"><td colspan="7">
                <div class="settings-providers-editor">
                    {% for ak in pyview.expanded_keys %}
                    <div class="provider-card-row" style="margin-bottom:4px">
                        <span style="font-size:11px;color:var(--muted);min-width:60px">{{ ak.comment }}</span>
                        <code style="flex:1;font-size:12px;padding:4px 8px;background:var(--surface);border-radius:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ ak.display }}</code>
                        {% if ak.cooldown_text %}
                        <span class="provider-card-btn provider-card-btn-ghost" style="font-size:10px;padding:3px 8px;color:#b7791f">{{ ak.cooldown_text }}</span>
                        {% endif %}
                        <button type="button" class="provider-card-btn provider-card-btn-ghost" style="font-size:10px;padding:3px 8px" onclick="pyview.toggle_key_enabled({{ ak.pk }})">{{ 'Disable' if ak.enabled else 'Enable' }}</button>
                        <button type="button" class="provider-card-btn provider-card-btn-danger" style="font-size:10px;padding:3px 8px" onclick="pyview.delete_key({{ ak.pk }})">Delete</button>
                    </div>
                    {% endfor %}
                    <div class="provider-card-row" style="margin-top:4px;gap:4px">
                        <input type="text" class="provider-card-input" id="comment_{{pyview.uid}}_{{ row.id }}" placeholder="Name" style="min-width:80px;flex:0 0 100px" autocomplete="off">
                        <input type="{{ pyview.input_type }}" class="provider-card-input" id="newkey_{{pyview.uid}}_{{ row.id }}" placeholder="paste api key here" style="min-width:140px" autocomplete="off">
                        <button type="button" class="provider-card-btn provider-card-btn-primary" onclick="pyview.add_key(
                            document.getElementById('newkey_{{pyview.uid}}_{{ row.id }}').value,
                            document.getElementById('comment_{{pyview.uid}}_{{ row.id }}').value
                        )">Add</button>
                        <button type="button" class="provider-card-btn provider-card-btn-ghost" onclick="pyview.toggle_key_visibility()">{{ pyview.key_visibility_btn }}</button>
                    </div>
                    {% if row.setup_instructions %}
                    <div class="provider-card-hint" style="margin-top:6px">{{ row.setup_instructions }}</div>
                    {% endif %}
                </div>
            </td></tr>
            {% endif %}
            {% endfor %}
            </tbody>
        </table>
        {% else %}
        <div class="settings-empty">No providers configured.</div>
        {% endif %}
    '''

    NUMERIC_COLS = ("models",)

    def __init__(self, subject: UiApp, parent: SettingsView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._expanded_id: int | None = None
        self._detail_id: int | None = None
        self._keys_revealed = False
        self._sort_col = "name"
        self._sort_desc = False
        self._probe_results: dict[int, dict] = {}
        self._probe_model_for: dict[int, int] = {}  # provider_id -> model_pk

    # ------------------------------------------------------------------
    # Rows
    # ------------------------------------------------------------------

    @property
    def provider_rows(self) -> list[dict]:
        providers = (
            # Show enabled providers plus any disabled provider that still
            # carries user-added API keys, so keys are never hidden by an
            # auto-disable pass.
            ApiProvider.objects.filter(
                _Q(enabled=True) | _Q(api_keys__isnull=False)
            ).distinct()
            .order_by("is_local", "name")
            .prefetch_related("api_keys")
        )
        rows = []
        for provider in providers:
            keys = [k for k in provider.api_keys.all() if k.enabled]
            if provider.default_api_key:
                key_state, key_count = "built-in", 0
            elif keys:
                key_state, key_count = "keys", len(keys)
            else:
                key_state, key_count = "none", 0

            last_usage = "—"
            if provider.last_usage:
                last_usage = provider.last_usage.strftime("%Y-%m-%d %H:%M:%S")

            rows.append({
                "id": provider.pk,
                "name": provider.name,
                "is_local": provider.is_local,
                "model_count": provider.aimodels.filter(enabled=True).count(),
                "limits": _limits_str(provider),
                "key_state": key_state,
                "key_count": key_count,
                "description": _provider_description(provider),
                "api_key_url": provider.api_key_url,
                "setup_instructions": provider.setup_instructions,
                "last_usage": last_usage,
                "probe": self._probe_results.get(provider.pk),
            })

        return sort_provider_rows(rows, self._sort_col, self._sort_desc)

    def _expanded_provider(self) -> ApiProvider | None:
        if self._expanded_id is None:
            return None
        return ApiProvider.objects.filter(pk=self._expanded_id).first()

    @property
    def expanded_keys(self) -> list[dict]:
        from django.utils import timezone

        provider = self._expanded_provider()
        if provider is None:
            return []
        result = []
        for k in provider.api_keys.all().order_by("-enabled", "pk"):
            key_str = k.key
            if not self._keys_revealed and len(key_str) > 8:
                display = key_str[:4] + "…" + key_str[-4:]
            else:
                display = key_str
            cooldown_text = ""
            if k.rate_limit_until and timezone.now() < k.rate_limit_until:
                remaining = int((k.rate_limit_until - timezone.now()).total_seconds())
                cooldown_text = f"cooling down {remaining // 60}m{remaining % 60:02d}s"
            result.append({
                "pk": k.pk,
                "comment": k.comment or "",
                "display": display,
                "enabled": k.enabled,
                "cooldown_text": cooldown_text,
            })
        return result

    @property
    def key_visibility_btn(self) -> str:
        return "Hide keys" if self._keys_revealed else "Reveal all"

    @property
    def input_type(self) -> str:
        return "text" if self._keys_revealed else "password"

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def toggle_expanded(self, provider_id: int) -> None:
        provider_id = int(provider_id)
        self._expanded_id = None if self._expanded_id == provider_id else provider_id
        self.update()

    def apply_sort(self, col: str) -> None:
        """Header click: toggle direction on repeat, else sort the column
        (names/limits ascending, numbers/keys descending)."""
        if col not in ("name", "models", "limits", "key"):
            return
        if col == self._sort_col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            self._sort_desc = col in self.NUMERIC_COLS or col == "key"
        self.update()

    def sort_arrow(self, col: str) -> str:
        if col != self._sort_col:
            return ""
        return " ▼" if self._sort_desc else " ▲"

    def open_provider(self, provider_id: int) -> None:
        """Show the provider detail (description, models, stats) in the rightbar."""
        from ui.main.rightpanel.provider.rightpanel_provider import RightPanelProvider

        try:
            provider = ApiProvider.objects.filter(pk=int(provider_id)).first()
        except (TypeError, ValueError):
            return
        if provider is None:
            return
        self._detail_id = provider.pk
        rightpanel = self._find_rightpanel()
        if rightpanel is not None:
            rightpanel.set_view(RightPanelProvider, provider)
        self.update()

    def clear_detail(self) -> None:
        """Forget the rightbar selection (called when leaving the section)."""
        self._detail_id = None

    def _find_rightpanel(self):
        parent = self.parent
        while parent is not None and not hasattr(parent, "rightpanel"):
            parent = getattr(parent, "parent", None)
        return getattr(parent, "rightpanel", None) if parent is not None else None

    def open_add(self, provider_id: int) -> None:
        self._expanded_id = int(provider_id)
        self.update()

    def toggle_key_visibility(self):
        self._keys_revealed = not self._keys_revealed
        self.update()

    def toggle_key_enabled(self, key_pk: int):
        provider = self._expanded_provider()
        if provider is None:
            return
        try:
            ak = ApiKey.objects.get(pk=key_pk, api_provider=provider)
            ak.enabled = not ak.enabled
            ak.save(update_fields=["enabled"])
        except ApiKey.DoesNotExist:
            pass
        self.update()

    def add_key(self, key_value: str, comment: str = ""):
        provider = self._expanded_provider()
        if provider is None:
            return
        key_value = (key_value or "").strip()
        if not key_value:
            return
        ApiKey.objects.create(
            api_provider=provider,
            key=key_value,
            comment=comment.strip() or None,
        )
        self.update()

    def delete_key(self, key_pk: int):
        provider = self._expanded_provider()
        if provider is None:
            return
        ApiKey.objects.filter(pk=key_pk, api_provider=provider).delete()
        self.update()

    def _resolve_session(self):
        """Resolve the active chat session (if any) for dispatching a test call."""
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

    def test_provider(self, provider_id: int) -> None:
        """Smoke-test a provider via a real test session."""
        from runtime.test_run import best_usable_model
        from server.tasks.probe_model import probe_model

        pid = int(provider_id)
        model = best_usable_model(pid)
        if model is None:
            self._probe_results[pid] = {
                "verdict": "failed",
                "error_message": "No usable enabled model on this provider",
            }
            self.update()
            return

        self._probe_results[pid] = {
            "verdict": "running",
            "model": model.name,
            "model_pk": model.pk,
        }
        self._probe_model_for[pid] = model.pk
        self.update()

        try:
            orm_subscribe(self, f"AiModel.pk:{model.pk}", self._on_probe_event)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        try:
            probe_model.delay(model.pk)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._probe_results[pid] = {
                "verdict": "failed",
                "error_message": str(exc),
            }
            self.update()

    def _on_probe_event(self, key=None, model=None, pk=None, action=None, data=None, **_kw):
        try:
            payload = None
            if isinstance(data, dict) and "probe" in data:
                payload = data["probe"]
            if payload is None:
                from server.tasks.probe_model import get_cached_result
                payload = get_cached_result(int(pk)) if pk is not None else None
            if payload is None:
                return
            pid = None
            for p, mpk in self._probe_model_for.items():
                if mpk == pk:
                    pid = p
                    break
            if pid is None:
                return
            self._probe_results[pid] = payload
            self.update()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _poll_probe(self, provider_id: int) -> None:
        pid = int(provider_id)
        mpk = self._probe_model_for.get(pid)
        if mpk is None:
            return
        try:
            from server.tasks.probe_model import get_cached_result
            cached = get_cached_result(mpk)
            if cached is not None:
                self._probe_results[pid] = cached
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
            main_view = None
            cur = self
            seen = set()
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
