from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from server.models.providers.api_provider import ApiProvider
from server.models.providers.api_key import ApiKey
from server.models.providers.ai_model import AiModel

class AiModelItemView(PyHtmlView):
    DOM_ELEMENT = "li"
    DOM_ELEMENT_CLASS = "provider-detail-item"
    TEMPLATE_STR = """
        <span class="provider-detail-item-name">{{ pyview.subject.name }}
         {% if pyview.subject.visition %}
        <u><i class="fa fa-eye"></i></u>
        {% endif %}
        {% if pyview.subject.is_cloud %}
            cloud
        {% else %}
            local
        {% endif %}
        </span>
        
        
        <div class="table-item-actions">
            <button class="btn btn-xs btn-danger delete-model-btn" title="Delete Model" onclick="pyview.delete_model()">
                <i class="fa fa-trash"></i>
            </button>
        </div>
        <div class="model-stats">
            <span title="Total LLM Queries">Q: {{ pyview.subject.total_llm_queries}}</span>
            <span title="Total Prompt Tokens">P: {{ pyview.subject.total_prompt_tokens}}</span>
            <span title="Total Completion Tokens">C: {{ pyview.subject.total_completion_tokens}}</span>
        </div>
    """
    def delete_model(self):
        self.subject.delete()
        self.parent.update()

class ApiKeyItemView(PyHtmlView):
    DOM_ELEMENT = "li"
    DOM_ELEMENT_CLASS = "provider-detail-item"
    TEMPLATE_STR = """
        <span class="provider-detail-item-name">{{ pyview.subject.comment or 'API Key' }}</span>
        <div class="table-item-actions">
            <button class="btn btn-xs btn-danger delete-apikey-btn" title="Delete API Key" onclick="pyview.delete_key()">
                <i class="fa fa-trash"></i>
            </button>
        </div>
        <div class="apikey-stats">
            <span title="Total LLM Queries">Q: {{ pyview.subject.total_llm_queries }}</span>
            <span title="Total Prompt Tokens">P: {{ pyview.subject.total_prompt_tokens }}</span>
            <span title="Total Completion Tokens">C: {{ pyview.subject.total_completion_tokens }}</span>
        </div>
    """
    def delete_key(self):
        self.subject.delete()
        self.parent.update()

class ProviderListItemView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="provider-block" id="provider_{{ pyview.subject.id }}">
        <div class="provider-summary">
            <div class="provider-info">
                <span class="provider-name">{{ pyview.subject.name }}</span>
                {% if pyview.subject.url %}
                    <a href="{{ pyview.subject.url }}" target="_blank" class="provider-url">{{ pyview.subject.url }}</a>
                {% endif %}
            </div>
            <div class="provider-actions">
                <button class="btn btn-xs btn-default" title="Edit Provider" onclick="pyview.toggle_edit()">
                    <i class="fa fa-pencil"></i>
                </button>
                <button class="btn btn-xs btn-danger delete-provider-btn" title="Delete Provider" onclick="pyview.delete_provider()">
                    <i class="fa fa-trash"></i>
                </button>
            </div>
            <div class="provider-stats">
                <span title="Total LLM Queries">Queries: {{ pyview.subject.total_llm_queries }}</span>
                <span title="Total Prompt Tokens">Prompt: {{ pyview.subject.total_prompt_tokens }}</span>
                <span title="Total Completion Tokens">Completion: {{ pyview.subject.total_completion_tokens }}</span>
            </div>
        </div>

        {% if pyview.is_editing %}
        <div class="inline-form edit-provider-form" style="padding: 15px; background: #fff; border: 1px solid #ddd; border-radius: 4px; margin: 10px;">
            <div class="modal-header" style="padding:0; border:0; margin-bottom:10px;">
                <h4 style="margin:0;">Edit API Provider</h4>
            </div>
            <div class="form-group">
                <label>Provider Name:</label>
                <input type="text" id="edit_name_{{ pyview.subject.id }}" class="form-control" value="{{ pyview.subject.name }}">
            </div>
            <div class="form-group">
                <label>Provider URL:</label>
                <input type="url" id="edit_url_{{ pyview.subject.id }}" class="form-control" value="{{ pyview.subject.url }}">
            </div>
            <div style="margin-top: 10px; text-align: right;">
                <button class="btn btn-secondary" onclick="pyview.toggle_edit()">Cancel</button>
                <button class="btn btn-primary" onclick="pyview.update_provider(document.getElementById('edit_name_{{ pyview.subject.id }}').value, document.getElementById('edit_url_{{ pyview.subject.id }}').value)">Save Changes</button>
            </div>
        </div>
        {% endif %}

        <div class="provider-details-content">
            <div class="provider-section">
                <h4>Models</h4>
                <ul class="provider-detail-list">
                    {% if pyview.model_views %}
                        {% for mview in pyview.model_views %}
                            {{ mview.render() }}
                        {% endfor %}
                    {% else %}
                        <li class="no-items-message">No models configured.</li>
                    {% endif %}
                </ul>
                <div class="add-item-container">
                    <input type="text" id="add_model_input_{{ pyview.subject.id }}" class="form-control input-xs add-model-input" placeholder="Add model name..." onkeypress="if(event.key === 'Enter') pyview.add_model(document.getElementById('add_model_input_{{ pyview.subject.id }}').value)">
                    <button class="btn btn-xs btn-default add-model-btn" title="Add Model" onclick="pyview.add_model(document.getElementById('add_model_input_{{ pyview.subject.id }}').value)">
                        <i class="fa fa-plus"></i>
                    </button>
                </div>
            </div>

            <div class="provider-section">
                <h4>API Keys</h4>
                <ul class="provider-detail-list">
                    {% if pyview.key_views %}
                        {% for kview in pyview.key_views %}
                            {{ kview.render() }}
                        {% endfor %}
                    {% else %}
                        <li class="no-items-message">No API keys configured.</li>
                    {% endif %}
                </ul>
                
                {% if pyview.show_add_key_form %}
                <div class="inline-form add-key-form" style="padding: 10px; border: 1px solid #eee; border-radius: 4px; margin-top: 10px; background: #fdfdfd;">
                    <div class="modal-header" style="padding:0; border:0; margin-bottom:5px;">
                        <h5 style="margin:0;">Add API Key</h5>
                    </div>
                    <div class="form-group">
                        <label>API Key:</label>
                        <input type="text" id="add_key_input_{{ pyview.subject.id }}" class="form-control">
                    </div>
                    <div class="form-group">
                        <label>Comment (Optional):</label>
                        <input type="text" id="add_key_comment_{{ pyview.subject.id }}" class="form-control" placeholder="e.g., Personal Key">
                    </div>
                    <div style="text-align: right; margin-top: 5px;">
                        <button class="btn btn-xs btn-secondary" onclick="pyview.toggle_add_key()">Cancel</button>
                        <button class="btn btn-xs btn-primary" onclick="pyview.save_key(document.getElementById('add_key_input_{{ pyview.subject.id }}').value, document.getElementById('add_key_comment_{{ pyview.subject.id }}').value)">Save Key</button>
                    </div>
                </div>
                {% else %}
                    <div class="add-item-container">
                        <button class="btn btn-xs btn-default add-apikey-btn" title="Add API Key" onclick="pyview.toggle_add_key()">
                            <i class="fa fa-plus"></i> Add Key
                        </button>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_editing = False
        self.show_add_key_form = False
        self.model_views = []
        self.key_views = []
        self._rebuild_subviews()

    def _rebuild_subviews(self):
        self.aimodels = list(self.subject.aimodels.all())
        self.apikeys = list(self.subject.api_keys.all())
        self.model_views = [AiModelItemView(m, self) for m in self.aimodels]
        self.key_views = [ApiKeyItemView(k, self) for k in self.apikeys]

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
            self.subject.url = url
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

class TabProvidersView(PyHtmlView):
    TEMPLATE_STR = """
    <div id="tabContent_providers" class="resizable-container tab-content flex-column active" style="padding: 20px; overflow-y: auto;">
        <div id="providers-list-header" class="sidebar-list-header">
            <span>API Providers</span>
            <button id="add-provider-btn" class="btn btn-xs btn-default" title="Add New Provider" onclick="pyview.toggle_add_provider()">
                <i class="fa fa-plus"></i>
            </button>
        </div>

        {% if pyview.show_add_form %}
        <div id="addProviderModal" class="inline-form" style="padding: 20px; background: #fff; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 20px;">
            <div class="modal-header" style="border:0; padding:0; margin-bottom:15px;">
                <h3 style="margin:0;">Add New API Provider</h3>
            </div>
            <div class="modal-body" style="padding:0;">
                <div class="form-group">
                    <label for="providerName">Provider Name:</label>
                    <input type="text" id="providerName" class="form-control" required>
                </div>
                <div class="form-group">
                    <label for="providerUrl">Provider URL:</label>
                    <input type="url" id="providerUrl" class="form-control" placeholder="https://api.example.com/v1">
                </div>
            </div>
            <div class="modal-footer" style="padding:0; border:0; margin-top: 15px; text-align: right;">
                <button class="btn btn-secondary" onclick="pyview.toggle_add_provider()">Cancel</button>
                <button id="saveProviderBtn" class="btn btn-primary" onclick="pyview.save_provider(document.getElementById('providerName').value, document.getElementById('providerUrl').value)">Save Provider</button>
            </div>
        </div>
        {% endif %}

        <div id="providers-list-body" class="sidebar-list-body" style="padding-top: 10px;">
            {% if pyview.provider_views %}
                {% for pview in pyview.provider_views %}
                    {{ pview.render() }}
                {% endfor %}
            {% else %}
                 <p style="padding: 40px; text-align: center; color: #999; font-style: italic;">No API providers configured yet.</p>
            {% endif %}
        </div>
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.show_add_form = False
        self.provider_views = []
        self._rebuild_provider_views()

    def _rebuild_provider_views(self):
        self.providers = list(ApiProvider.objects.all())
        self.provider_views = [ProviderListItemView(p, self) for p in self.providers]

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
