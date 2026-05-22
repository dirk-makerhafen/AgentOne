from __future__ import annotations
from ui.lib.model_view import ModelView
from server.models.system import System, SystemStatus, SystemOS, SystemConnectionMode


class SystemListItemView(ModelView):
    DOM_ELEMENT_CLASS = "SystemListItemView"

    TEMPLATE_STR = """
    <div class="system-card" id="system_{{ pyview.subject.id }}">
        <div class="system-card-header">
            <span class="system-name">{{ pyview.subject.name }}</span>
            <span class="system-status-badge status-{{ pyview.subject.status }}">
                {{ pyview.subject.get_status_display() }}
            </span>
            <span class="system-card-meta">
                {{ pyview.subject.get_executor_mode_display() }}
                {% if pyview.subject.executor_url %}· {{ pyview.subject.executor_url }}{% endif %}
                {% if pyview.subject.last_heartbeat %}· {{ pyview.subject.last_heartbeat }}{% endif %}
            </span>
            <div class="system-card-actions">
                <button class="btn btn-xs btn-default" onclick="pyview.toggle_edit()">
                    <i class="fa fa-pencil"></i>
                </button>
                <button class="btn btn-xs btn-danger" onclick="pyview.delete_system()">
                    <i class="fa fa-trash"></i>
                </button>
            </div>
        </div>

        {% if pyview.is_editing %}
        <div class="inline-form" style="border-radius:0; border-left:none; border-right:none; border-top:none;">
            <h4>Edit system</h4>
            <div class="form-group"><label>Name</label>
                <input type="text" id="es_{{ pyview.subject.id }}_name" class="form-control" value="{{ pyview.subject.name }}">
            </div>
            <div class="form-group"><label>Description</label>
                <textarea id="es_{{ pyview.subject.id }}_desc" class="form-control">{{ pyview.subject.description }}</textarea>
            </div>
            <div class="form-group"><label>Status</label>
                <select id="es_{{ pyview.subject.id }}_status" class="form-control">
                    {% for v, l in pyview.status_choices %}
                        <option value="{{ v }}" {{ 'selected' if v == pyview.subject.status else '' }}>{{ l }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group"><label>OS</label>
                <select id="es_{{ pyview.subject.id }}_os" class="form-control">
                    {% for v, l in pyview.os_choices %}
                        <option value="{{ v }}" {{ 'selected' if v == pyview.subject.os else '' }}>{{ l }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group"><label>Connection mode</label>
                <select id="es_{{ pyview.subject.id }}_mode" class="form-control">
                    {% for v, l in pyview.connection_mode_choices %}
                        <option value="{{ v }}" {{ 'selected' if v == pyview.subject.executor_mode else '' }}>{{ l }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group"><label>Executor URL</label>
                <input type="url" id="es_{{ pyview.subject.id }}_url" class="form-control" value="{{ pyview.subject.executor_url }}">
            </div>
            <div class="form-group"><label>Executor API key</label>
                <input type="text" id="es_{{ pyview.subject.id }}_apikey" class="form-control" value="{{ pyview.subject.executor_api_key }}">
            </div>
            <div style="display:flex; gap:8px; justify-content:flex-end; margin-top:8px;">
                <button class="btn btn-default" onclick="pyview.toggle_edit()">Cancel</button>
                <button class="btn btn-primary" onclick="pyview.save_edit(
                    document.getElementById('es_{{ pyview.subject.id }}_name').value,
                    document.getElementById('es_{{ pyview.subject.id }}_desc').value,
                    document.getElementById('es_{{ pyview.subject.id }}_status').value,
                    document.getElementById('es_{{ pyview.subject.id }}_os').value,
                    document.getElementById('es_{{ pyview.subject.id }}_mode').value,
                    document.getElementById('es_{{ pyview.subject.id }}_url').value,
                    document.getElementById('es_{{ pyview.subject.id }}_apikey').value)">
                    Save
                </button>
            </div>
        </div>
        {% endif %}
    </div>
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_editing = False
        self.status_choices = SystemStatus.choices
        self.os_choices = SystemOS.choices
        self.connection_mode_choices = SystemConnectionMode.choices

    def toggle_edit(self):
        self.is_editing = not self.is_editing
        self.update()

    def save_edit(self, name, description, status, os, executor_mode, executor_url, executor_api_key):
        if name:
            self.subject.name = name
            self.subject.description = description
            self.subject.status = status
            self.subject.os = os
            self.subject.executor_mode = executor_mode
            self.subject.executor_url = executor_url
            self.subject.executor_api_key = executor_api_key
            self.subject.save()
        self.is_editing = False
        self.parent.update()

    def delete_system(self):
        self.subject.delete()
        self.parent.update()


class SystemsView(ModelView):
    TEMPLATE_STR = """
    <div class="systems-view">
        <div class="sidebar-list-header">
            <span>Systems</span>
            <button class="btn btn-xs btn-default" onclick="pyview.toggle_add_system()">
                <i class="fa fa-plus"></i>
            </button>
        </div>

        {% if pyview.show_add_form %}
        <div class="inline-form" style="margin: 12px 16px;">
            <h4>Add system</h4>
            <div class="form-group"><label>Name</label>
                <input type="text" id="systemName" class="form-control" required></div>
            <div class="form-group"><label>Description</label>
                <textarea id="systemDescription" class="form-control"></textarea></div>
            <div class="form-group"><label>Status</label>
                <select id="systemStatus" class="form-control">
                    {% for v, l in pyview.status_choices %}<option value="{{ v }}">{{ l }}</option>{% endfor %}
                </select></div>
            <div class="form-group"><label>OS</label>
                <select id="systemOs" class="form-control">
                    {% for v, l in pyview.os_choices %}<option value="{{ v }}">{{ l }}</option>{% endfor %}
                </select></div>
            <div class="form-group"><label>Connection mode</label>
                <select id="systemConnectionMode" class="form-control">
                    {% for v, l in pyview.connection_mode_choices %}<option value="{{ v }}">{{ l }}</option>{% endfor %}
                </select></div>
            <div class="form-group"><label>Executor URL</label>
                <input type="url" id="systemExecutorUrl" class="form-control" placeholder="http://1.2.3.4:8000"></div>
            <div class="form-group"><label>Executor API key</label>
                <input type="text" id="systemExecutorApiKey" class="form-control"></div>
            <div style="display:flex; gap:8px; justify-content:flex-end;">
                <button class="btn btn-default" onclick="pyview.toggle_add_system()">Cancel</button>
                <button class="btn btn-primary" onclick="pyview.save_system(
                    document.getElementById('systemName').value,
                    document.getElementById('systemDescription').value,
                    document.getElementById('systemStatus').value,
                    document.getElementById('systemOs').value,
                    document.getElementById('systemConnectionMode').value,
                    document.getElementById('systemExecutorUrl').value,
                    document.getElementById('systemExecutorApiKey').value)">
                    Save system
                </button>
            </div>
        </div>
        {% endif %}

        <div class="systems-list">
            {% if pyview.system_views %}
                {% for sv in pyview.system_views %}{{ sv.render() }}{% endfor %}
            {% else %}
                <p class="systems-empty">No systems configured yet.</p>
            {% endif %}
        </div>
    </div>
    """

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.show_add_form = False
        self.system_views = []
        self.status_choices = SystemStatus.choices
        self.os_choices = SystemOS.choices
        self.connection_mode_choices = SystemConnectionMode.choices
        self._rebuild_system_views()

    def _rebuild_system_views(self):
        self.system_views = [SystemListItemView(s, self) for s in System.objects.all()]

    def update(self):
        self._rebuild_system_views()
        super().update()

    def _on_subject_updated(self, source, **kwargs):
        self.update()

    def toggle_add_system(self):
        self.show_add_form = not self.show_add_form
        self.update()

    def save_system(self, name, description, status, os, executor_mode, executor_url, executor_api_key):
        if name:
            System.objects.create(
                name=name, description=description, status=status, os=os,
                executor_mode=executor_mode, executor_url=executor_url,
                executor_api_key=executor_api_key,
            )
            self.show_add_form = False
            self.update()