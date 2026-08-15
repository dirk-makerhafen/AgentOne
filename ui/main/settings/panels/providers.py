from __future__ import annotations
from typing import TYPE_CHECKING
from django.db.models import Q
from server.models.providers.api_provider import ApiProvider
from server.models.providers.api_key import ApiKey
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
from api.utils import sync_provider_models

if TYPE_CHECKING:
    from ui.main.settings.settings import SettingsView


class ProviderCardView(ModelView):
    TEMPLATE_STR = '''
        <button type="button" class="provider-card-header" onclick="pyview.toggle_open()">
            <div class="provider-card-info">
                <div class="provider-card-name">{{ pyview.subject.name }}</div>
                <div class="provider-card-meta">{{ pyview.model_count }} models · {{ pyview.status_text }}</div>
            </div>
            {% if pyview.api_key_url %}
            <a href="{{ pyview.api_key_url }}" target="_blank" class="provider-card-badge" onclick="event.stopPropagation()" style="text-decoration:none">Get API key</a>
            {% endif %}
            <svg class="provider-card-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" width="16" height="16"><path d="M6 9l6 6 6-6"></path></svg>
        </button>
        <div class="provider-card-body">
            <div class="provider-card-field">
                <label class="provider-card-label">API keys</label>
                {% for ak in pyview.api_keys %}
                <div class="provider-card-row" style="margin-bottom:4px">
                    <span style="font-size:11px;color:var(--muted);min-width:60px">{{ ak.comment }}</span>
                    <code style="flex:1;font-size:12px;padding:4px 8px;background:var(--surface);border-radius:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ ak.display }}</code>
                    <button type="button" class="provider-card-btn provider-card-btn-ghost" style="font-size:10px;padding:3px 8px" onclick="pyview.toggle_key_enabled({{ ak.pk }})">{{ 'Disable' if ak.enabled else 'Enable' }}</button>
                    <button type="button" class="provider-card-btn provider-card-btn-danger" style="font-size:10px;padding:3px 8px" onclick="pyview.delete_key({{ ak.pk }})">Delete</button>
                </div>
                {% endfor %}
                <div class="provider-card-row" style="margin-top:4px;gap:4px">
                    <input type="text" class="provider-card-input" id="comment_{{pyview.uid}}" placeholder="Label (optional)" style="min-width:80px;flex:0 0 100px" autocomplete="off">
                    <input type="{{ pyview.input_type }}" class="provider-card-input" id="newkey_{{pyview.uid}}" placeholder="sk-..." style="min-width:140px" autocomplete="off">
                    <button type="button" class="provider-card-btn provider-card-btn-primary" onclick="pyview.add_key(
                        document.getElementById('newkey_{{pyview.uid}}').value,
                        document.getElementById('comment_{{pyview.uid}}').value
                    )">Add</button>
                    <button type="button" class="provider-card-btn provider-card-btn-ghost" onclick="pyview.toggle_key_visibility()">{{ pyview.key_visibility_btn }}</button>
                </div>
            </div>
            {% if pyview.setup_instructions %}
            <div class="provider-card-hint" style="margin-top:6px">{{ pyview.setup_instructions }}</div>
            {% endif %}
            <div class="provider-card-models" style="margin-top:10px">
                <div class="provider-card-label">Models</div>
                <div class="provider-card-model-tags">
                    {% for tag in pyview.model_tags %}
                    <span class="provider-card-model-tag">{{ tag }}</span>
                    {% endfor %}
                </div>
            </div>
            <div class="provider-card-row" style="margin-top:6px">
                <button type="button" class="provider-card-btn provider-card-btn-ghost" style="display:flex;align-items:center;gap:5px" onclick="pyview.refresh_models()">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path><path d="M21 3v5h-5"></path><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"></path><path d="M3 21v-5h5"></path></svg>
                    Refresh models
                </button>
            </div>
        </div>
    '''

    def __init__(self, subject: ApiProvider, parent: QuerySetView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._is_open = False
        self._keys_revealed = False

    @property
    def DOM_ELEMENT_CLASS(self):
        cls = "provider-card"
        if self._is_open:
            cls += " open"
        return cls

    @property
    def model_count(self) -> int:
        return self._model_qs().count()

    def _model_qs(self):
        """Models shown on this card, filtered to the provider's section.

        A local provider (e.g. Ollama) can still serve cloud models, so its
        card only lists local/self-hosted models — cloud ones are excluded.
        """
        qs = self.subject.aimodels.all().order_by("name")
        if self.subject.is_local:
            return qs.filter(is_cloud=False).exclude(
                Q(name__endswith="-cloud") | Q(name__endswith=":cloud")
            )
        return qs.filter(is_cloud=True)

    @property
    def model_tags(self) -> list[str]:
        return list(self._model_qs().values_list("name", flat=True)[:100])

    @property
    def status_text(self) -> str:
        count = self.subject.api_keys.filter(enabled=True).count()
        if count == 0:
            return "Not configured"
        return f"{count} key(s) configured"

    @property
    def api_key_url(self) -> str:
        info = getattr(self.subject, "data", None) or {}
        return info.get("api_key_url", "")

    @property
    def setup_instructions(self) -> str:
        info = getattr(self.subject, "data", None) or {}
        return info.get("setup_instructions", "")

    @property
    def key_visibility_btn(self) -> str:
        return "Hide keys" if self._keys_revealed else "Reveal all"

    @property
    def input_type(self) -> str:
        return "text" if self._keys_revealed else "password"

    @property
    def api_keys(self) -> list[dict]:
        qs = self.subject.api_keys.all().order_by("-enabled", "pk")
        result = []
        for k in qs:
            key_str = k.key
            if not self._keys_revealed and len(key_str) > 8:
                display = key_str[:4] + "…" + key_str[-4:]
            else:
                display = key_str
            result.append({
                "pk": k.pk,
                "comment": k.comment or "",
                "display": display,
                "enabled": k.enabled,
            })
        return result

    def toggle_open(self):
        self._is_open = not self._is_open
        self.update()

    def toggle_key_visibility(self):
        self._keys_revealed = not self._keys_revealed
        self.update()

    def toggle_key_enabled(self, key_pk: int):
        try:
            ak = ApiKey.objects.get(pk=key_pk, api_provider=self.subject)
            ak.enabled = not ak.enabled
            ak.save(update_fields=["enabled"])
        except ApiKey.DoesNotExist:
            pass
        self.update()

    def add_key(self, key_value: str, comment: str = ""):
        key_value = key_value.strip()
        if not key_value:
            return
        ApiKey.objects.create(
            api_provider=self.subject,
            key=key_value,
            comment=comment.strip() or None,
        )
        self.update()

    def delete_key(self, key_pk: int):
        ApiKey.objects.filter(pk=key_pk, api_provider=self.subject).delete()
        self.update()

    def refresh_models(self):
        result = sync_provider_models(self.subject.pk)
        if result["error"]:
            msg = f"Sync failed: {result['error']}"
        else:
            msg = f"Synced: {result['created']} created, {result['updated']} updated, {result['total']} total"
        self.eval_javascript("alert(arg.message)", message=msg)
        self.update()


class SettingPanelProviders(ModelView):
    DOM_ELEMENT_CLASS = "settings-pane"
    TEMPLATE_STR = '''
        <div class="settings-section-head">
            <div>
                <div class="settings-section-title" data-i18n="providers_section_title">Providers</div>
                <div class="settings-section-meta" data-i18n="providers_section_meta">Manage API keys for AI providers. Changes take effect immediately.</div>
            </div>
        </div>
        <div class="settings-subsection">
            <div class="settings-subsection-title" data-i18n="providers_local_title">Local providers</div>
            <div class="settings-subsection-meta" data-i18n="providers_local_meta">Services running on this machine (e.g. Ollama). Only local/self-hosted models are listed.</div>
        </div>
        {% if pyview.has_local_providers %}
        <div style="display:flex;flex-direction:column;margin-top:4px">
            {{ pyview.local_provider_cards.render() }}
        </div>
        {% else %}
        <div class="settings-empty" data-i18n="providers_local_empty">No local providers configured.</div>
        {% endif %}
        <div class="settings-subsection">
            <div class="settings-subsection-title" data-i18n="providers_cloud_title">Cloud</div>
            <div class="settings-subsection-meta" data-i18n="providers_cloud_meta">Remote providers accessed over the internet. Add an API key to enable their models.</div>
        </div>
        {% if pyview.has_cloud_providers %}
        <div style="display:flex;flex-direction:column;margin-top:4px">
            {{ pyview.cloud_provider_cards.render() }}
        </div>
        {% else %}
        <div class="settings-empty" data-i18n="providers_cloud_empty">No cloud providers configured.</div>
        {% endif %}
    '''

    def __init__(self, subject, parent: SettingsView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.local_provider_cards = QuerySetView(
            subject=ApiProvider.objects.filter(is_local=True).order_by("name"),
            parent=self,
            item_class=ProviderCardView,
        )
        self.cloud_provider_cards = QuerySetView(
            subject=ApiProvider.objects.filter(is_local=False).order_by("name"),
            parent=self,
            item_class=ProviderCardView,
        )

    @property
    def has_local_providers(self) -> bool:
        return self.local_provider_cards.query.exists()

    @property
    def has_cloud_providers(self) -> bool:
        return self.cloud_provider_cards.query.exists()
