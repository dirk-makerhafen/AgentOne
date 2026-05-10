from __future__ import annotations
from ui.lib.model_view import ModelView
from server.models.providers.api_provider import ApiProvider
from server.models.providers.api_key import ApiKey
from server.models.providers.ai_model import AiModel


class AiModelItemView(ModelView):
    DOM_ELEMENT = "li"
    DOM_ELEMENT_CLASS = "provider-detail-item"
    TEMPLATE_STR = """
        <span class="provider-detail-item-name">
            {{ pyview.subject.name }}
            {% if pyview.subject.is_cloud %}
                <span class="badge">cloud</span>
            {% else %}
                <span class="badge">local</span>
            {% endif %}
            {% if pyview.subject.is_rate_limited()[0] %}
                <span class="badge badge--warning">rate limited</span>
            {% endif %}
        </span>
        <div class="item-stats">
            <span title="Queries">Q: {{ pyview.subject.total_llm_queries }}</span>
            <span title="Prompt tokens">P: {{ pyview.subject.total_prompt_tokens }}</span>
            <span title="Completion tokens">C: {{ pyview.subject.total_completion_tokens }}</span>
        </div>
        <div class="item-actions">
            <button class="btn btn-xs btn-danger" title="Delete model" onclick="pyview.delete_model()">
                <i class="fa fa-trash"></i>
            </button>
        </div>
    """

    def delete_model(self):
        self.subject.delete()
        self.parent.update()


class ApiKeyItemView(ModelView):
    DOM_ELEMENT = "li"
    DOM_ELEMENT_CLASS = "provider-detail-item"
    TEMPLATE_STR = """
        <span class="provider-detail-item-name">
            {{ pyview.subject.comment or 'API Key' }}
            {% if pyview.subject.is_rate_limited()[0] %}
                <span class="badge badge--warning">rate limited</span>
            {% endif %}
        </span>
        <div class="item-stats">
            <span title="Queries">Q: {{ pyview.subject.total_llm_queries }}</span>
            <span title="Prompt tokens">P: {{ pyview.subject.total_prompt_tokens }}</span>
            <span title="Completion tokens">C: {{ pyview.subject.total_completion_tokens }}</span>
        </div>
        <div class="item-actions">
            <button class="btn btn-xs btn-danger" title="Delete key" onclick="pyview.delete_key()">
                <i class="fa fa-trash"></i>
            </button>
        </div>
    """

    def delete_key(self):
        self.subject.delete()
        self.parent.update()


class ProviderListItemView(ModelView):
    TEMPLATE_STR = """
    <div class="provider-card">
        <div class="provider-card-header">
            <div class="provider-card-title">
                <span class="provider-name">{{ pyview.subject.name }}</span>
                {% if pyview.subject.url %}
                    <a href="{{ pyview.subject.url }}" target="_blank" class="provider-url">
                        {{ pyview.subject.url }}
                    </a>
                {% endif %}
            </div>
            <div class="provider-card-stats">
                <span title="Queries">{{ pyview.subject.total_llm_queries }} queries</span>
                <span title="Prompt tokens">{{ pyview.subject.total_prompt_tokens }} prompt</span>
                <span title="Completion tokens">{{ pyview.subject.total_completion_tokens }} completion</span>
            </div>
            <div class="provider-card-actions">
                <button class="btn btn-xs btn-default" title="Edit" onclick="pyview.toggle_edit()">
                    <i class="fa fa-pencil"></i>
                </button>
                <button class="btn btn-xs btn-danger" title="Delete" onclick="pyview.delete_provider()">
                    <i class="fa fa-trash"></i>
                </button>
            </div>
        </div>

        {% if pyview.is_editing %}
        <div class="inline-form" style="margin: 0; border-radius: 0; border-left: none; border-right: none;">
            <div class="form-group">
                <label>Name</label>
                <input type="text" id="edit_name_{{ pyview.subject.id }}" class="form-control" value="{{ pyview.subject.name }}">
            </div>
            <div class="form-group">
                <label>URL</label>
                <input type="url" id="edit_url_{{ pyview.subject.id }}" class="form-control" value="{{ pyview.subject.url }}">
            </div>
            <div style="display:flex; gap:8px; justify-content:flex-end;">
                <button class="btn btn-default" onclick="pyview.toggle_edit()">Cancel</button>
                <button class="btn btn-primary" onclick="pyview.update_provider(
                    document.getElementById('edit_name_{{ pyview.subject.id }}').value,
                    document.getElementById('edit_url_{{ pyview.subject.id }}').value)">
                    Save
                </button>
            </div>
        </div>
        {% endif %}

        <div class="provider-card-body">
            <!-- Models -->
            <div class="provider-section">
                <div class="provider-section-header">Models</div>
                <ul class="provider-detail-list">
                    {% for mview in pyview.model_views %}
                        {{ mview.render() }}
                    {% else %}
                        <li class="detail-empty">No models configured.</li>
                    {% endfor %}
                </ul>
                <div class="detail-add-row">
                    <input type="text" id="add_model_{{ pyview.subject.id }}"
                           class="form-control" placeholder="Model name…"
                           onkeypress="if(event.key==='Enter') pyview.add_model(document.getElementById('add_model_{{ pyview.subject.id }}').value)">
                    <button class="btn btn-xs btn-default"
                            onclick="pyview.add_model(document.getElementById('add_model_{{ pyview.subject.id }}').value)">
                        <i class="fa fa-plus"></i>
                    </button>
                </div>
            </div>

            <!-- API Keys -->
            <div class="provider-section">
                <div class="provider-section-header">API Keys</div>
                <ul class="provider-detail-list">
                    {% for kview in pyview.key_views %}
                        {{ kview.render() }}
                    {% else %}
                        <li class="detail-empty">No API keys configured.</li>
                    {% endfor %}
                </ul>

                {% if pyview.show_add_key_form %}
                <div class="inline-form" style="margin-top: 8px;">
                    <div class="form-group">
                        <label>API Key</label>
                        <input type="text" id="add_key_{{ pyview.subject.id }}" class="form-control">
                    </div>
                    <div class="form-group">
                        <label>Comment (optional)</label>
                        <input type="text" id="add_key_comment_{{ pyview.subject.id }}" class="form-control"
                               placeholder="e.g. Personal key">
                    </div>
                    <div style="display:flex; gap:8px; justify-content:flex-end;">
                        <button class="btn btn-default btn-xs" onclick="pyview.toggle_add_key()">Cancel</button>
                        <button class="btn btn-primary btn-xs"
                                onclick="pyview.save_key(
                                    document.getElementById('add_key_{{ pyview.subject.id }}').value,
                                    document.getElementById('add_key_comment_{{ pyview.subject.id }}').value)">
                            Save key
                        </button>
                    </div>
                </div>
                {% else %}
                    <div class="detail-add-row">
                        <button class="btn btn-xs btn-default" onclick="pyview.toggle_add_key()">
                            <i class="fa fa-plus"></i> Add key
                        </button>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
    """

    CSS_STR = """
.provider-card {
    margin: 12px 0;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--bg);
    box-shadow: var(--shadow-sm);
    overflow: hidden;
    transition: box-shadow 0.15s;
}
.provider-card:hover { box-shadow: var(--shadow-md); }

.provider-card-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 16px;
    background: var(--bg-subtle);
    border-bottom: 1px solid var(--border);
}

.provider-card-title {
    display: flex;
    flex-direction: column;
    flex-grow: 1;
    min-width: 0;
}
.provider-name {
    font-weight: 600;
    font-size: 1.05em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.provider-url {
    font-size: 0.8em;
    color: var(--text-muted);
    text-decoration: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.provider-url:hover { text-decoration: underline; }

.provider-card-stats {
    display: flex;
    gap: 12px;
    font-size: 0.8em;
    color: var(--text-faint);
    white-space: nowrap;
}
.provider-card-actions { display: flex; gap: 6px; flex-shrink: 0; }

.provider-card-body {
    display: flex;
    gap: 1px;
    background: var(--border);
}

.provider-section {
    flex: 1;
    padding: 12px;
    background: var(--bg);
    min-width: 0;
}
.provider-section-header {
    font-size: 0.75em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .05em;
    color: var(--text-muted);
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-light);
    margin-bottom: 6px;
}

.provider-detail-list {
    list-style: none;
    padding: 0;
    margin: 0 0 8px;
    border: 1px solid var(--border-light);
    border-radius: var(--r-sm);
    overflow: hidden;
}
.provider-detail-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 10px;
    border-bottom: 1px solid var(--border-light);
    font-size: 0.88em;
    transition: background 0.1s;
}
.provider-detail-item:last-child { border-bottom: none; }
.provider-detail-item:hover { background: var(--bg-subtle); }

.provider-detail-item-name { flex-grow: 1; }

.item-stats {
    display: flex;
    gap: 8px;
    font-size: 0.8em;
    color: var(--text-faint);
}
.item-actions { flex-shrink: 0; }

.detail-empty {
    padding: 10px;
    color: var(--text-faint);
    font-style: italic;
    font-size: 0.85em;
    text-align: center;
}
.detail-add-row {
    display: flex;
    gap: 6px;
    align-items: center;
    margin-top: 8px;
}
.detail-add-row .form-control { flex-grow: 1; }
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_editing = False
        self.show_add_key_form = False
        self.model_views = []
        self.key_views = []
        self._rebuild_subviews()

    def _rebuild_subviews(self):
        self.model_views = [AiModelItemView(m, self) for m in self.subject.aimodels.all()]
        self.key_views   = [ApiKeyItemView(k, self) for k in self.subject.api_keys.all()]

    def update(self):
        self._rebuild_subviews()
        super().update()

    def toggle_edit(self):
        self.is_editing = not self.is_editing
        self.update()

    def toggle_add_key(self):
        self.show_add_key_form = not self.show_add_key_form
        self.update()

    def update_provider(self, name, url):
        if name:
            self.subject.name = name
            self.subject.url  = url
            self.subject.save()
            self.is_editing = False
            self.update()

    def delete_provider(self):
        self.subject.delete()
        self.parent.update()

    def add_model(self, model_name):
        if model_name:
            AiModel.objects.create(name=model_name, api_provider=self.subject)
            self.update()

    def save_key(self, key_val, comment_val):
        if key_val:
            ApiKey.objects.create(key=key_val, comment=comment_val, api_provider=self.subject)
            self.show_add_key_form = False
            self.update()


class ProvidersView(ModelView):
    TEMPLATE_STR = """
    <div class="providers-view">
        <div class="sidebar-list-header">
            <span>API Providers</span>
            <button class="btn btn-xs btn-default" onclick="pyview.toggle_add_provider()">
                <i class="fa fa-plus"></i>
            </button>
        </div>

        {% if pyview.show_add_form %}
        <div class="inline-form" style="margin: 12px 16px;">
            <h4>Add API provider</h4>
            <div class="form-group">
                <label>Name</label>
                <input type="text" id="providerName" class="form-control" required>
            </div>
            <div class="form-group">
                <label>URL</label>
                <input type="url" id="providerUrl" class="form-control"
                       placeholder="https://api.example.com/v1">
            </div>
            <div style="display:flex; gap:8px; justify-content:flex-end;">
                <button class="btn btn-default" onclick="pyview.toggle_add_provider()">Cancel</button>
                <button class="btn btn-primary"
                        onclick="pyview.save_provider(
                            document.getElementById('providerName').value,
                            document.getElementById('providerUrl').value)">
                    Save provider
                </button>
            </div>
        </div>
        {% endif %}

        <div class="providers-list">
            {% if pyview.provider_views %}
                {% for pview in pyview.provider_views %}
                    {{ pview.render() }}
                {% endfor %}
            {% else %}
                <p class="providers-empty">No API providers configured yet.</p>
            {% endif %}
        </div>
    </div>
    """

    CSS_STR = """
.providers-view {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
}
.providers-list {
    flex-grow: 1;
    overflow-y: auto;
    padding: 0 16px 16px;
}
.providers-empty {
    padding: 40px;
    text-align: center;
    color: var(--text-faint);
    font-style: italic;
}
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.show_add_form = False
        self.provider_views = []
        self._rebuild_provider_views()

    def _rebuild_provider_views(self):
        self.provider_views = [
            ProviderListItemView(p, self)
            for p in ApiProvider.objects.all()
        ]

    def update(self):
        self._rebuild_provider_views()
        super().update()

    def _on_subject_updated(self, source, **kwargs):
        self.update()

    def toggle_add_provider(self):
        self.show_add_form = not self.show_add_form
        self.update()

    def save_provider(self, name, url):
        if name:
            ApiProvider.objects.create(name=name, url=url)
            self.show_add_form = False
            self.update()