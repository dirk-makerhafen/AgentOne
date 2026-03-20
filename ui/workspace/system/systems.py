from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from server.models.system import System, SystemStatus, SystemOS, SystemConnectionMode

class SystemListItemView(PyHtmlView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "provider-block" # Reusing some styles from providers
    TEMPLATE_STR = """
    <div class="system-block" id="system_{{ pyview.subject.id }}">
        <div class="system-summary">
            <div class="system-info">
                <span class="system-name">{{ pyview.subject.name }}</span>
                <span class="system-status status-{{ pyview.subject.status }}">{{ pyview.subject.get_status_display() }}</span>
            </div>
            <div class="system-actions">
                <button class="btn btn-xs btn-default" title="Edit System" onclick="pyview.toggle_edit()">
                    <i class="fa fa-pencil"></i>
                </button>
                <button class="btn btn-xs btn-danger delete-system-btn" title="Delete System" onclick="pyview.delete_system()">
                    <i class="fa fa-trash"></i>
                </button>
            </div>
            <div class="system-details">
                <span>Mode: {{ pyview.subject.get_executor_mode_display() }}</span>
                {% if pyview.subject.executor_url %}<span>URL: {{ pyview.subject.executor_url }}</span>{% endif %}
                {% if pyview.subject.last_heartbeat %}<span>Heartbeat: {{ pyview.subject.last_heartbeat }}</span>{% endif %}
            </div>
        </div>

        {% if pyview.is_editing %}
        <div class="inline-form edit-system-form" style="padding: 15px; background: #fff; border: 1px solid #ddd; border-radius: 4px; margin: 10px;">
            <div class="modal-header" style="padding:0; border:0; margin-bottom:10px;">
                <h4 style="margin:0;">Edit System</h4>
            </div>
            <div class="form-group">
                <label>System Name:</label>
                <input type="text" id="edit_system_name_{{ pyview.subject.id }}" class="form-control" value="{{ pyview.subject.name }}">
            </div>
            <div class="form-group">
                <label>Description:</label>
                <textarea id="edit_system_description_{{ pyview.subject.id }}" class="form-control">{{ pyview.subject.description }}</textarea>
            </div>
            <div class="form-group">
                <label>Status:</label>
                <select id="edit_system_status_{{ pyview.subject.id }}" class="form-control">
                    {% for choice_value, choice_label in pyview.status_choices %}
                        <option value="{{ choice_value }}" {{ 'selected' if choice_value == pyview.subject.status else '' }}>{{ choice_label }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label>OS:</label>
                <select id="edit_system_os_{{ pyview.subject.id }}" class="form-control">
                    {% for choice_value, choice_label in pyview.os_choices %}
                        <option value="{{ choice_value }}" {{ 'selected' if choice_value == pyview.subject.os else '' }}>{{ choice_label }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label>Connection Mode:</label>
                <select id="edit_system_executor_mode_{{ pyview.subject.id }}" class="form-control">
                    {% for choice_value, choice_label in pyview.connection_mode_choices %}
                        <option value="{{ choice_value }}" {{ 'selected' if choice_value == pyview.subject.executor_mode else '' }}>{{ choice_label }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label>Executor URL:</label>
                <input type="url" id="edit_system_executor_url_{{ pyview.subject.id }}" class="form-control" value="{{ pyview.subject.executor_url }}">
            </div>
            <div class="form-group">
                <label>Executor API Key:</label>
                <input type="text" id="edit_system_executor_api_key_{{ pyview.subject.id }}" class="form-control" value="{{ pyview.subject.executor_api_key }}">
            </div>
            <div style="margin-top: 10px; text-align: right;">
                <button class="btn btn-secondary" onclick="pyview.toggle_edit()">Cancel</button>
                <button class="btn btn-primary" onclick="pyview.update_system(
                    document.getElementById('edit_system_name_{{ pyview.subject.id }}').value, 
                    document.getElementById('edit_system_description_{{ pyview.subject.id }}').value, 
                    document.getElementById('edit_system_status_{{ pyview.subject.id }}').value,
                    document.getElementById('edit_system_os_{{ pyview.subject.id }}').value,
                    document.getElementById('edit_system_executor_mode_{{ pyview.subject.id }}').value,
                    document.getElementById('edit_system_executor_url_{{ pyview.subject.id }}').value,
                    document.getElementById('edit_system_executor_api_key_{{ pyview.subject.id }}').value
                )">Save Changes</button>
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

    def update_system(self, name, description, status, os, executor_mode, executor_url, executor_api_key):
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

class TabSystemsView(PyHtmlView):
    TEMPLATE_STR = """
    <div id="tabContent_systems" class="resizable-container tab-content flex-column active" style="padding: 20px; overflow-y: auto;">
        <div id="systems-list-header" class="sidebar-list-header">
            <span>Systems</span>
            <button id="add-system-btn" class="btn btn-xs btn-default" title="Add New System" onclick="pyview.toggle_add_system()">
                <i class="fa fa-plus"></i>
            </button>
        </div>

        {% if pyview.show_add_form %}
        <div id="addSystemModal" class="inline-form" style="padding: 20px; background: #fff; border: 1px solid #ddd; border-radius: 4px; margin-bottom: 20px;">
            <div class="modal-header" style="border:0; padding:0; margin-bottom:15px;">
                <h3 style="margin:0;">Add New System</h3>
            </div>
            <div class="modal-body" style="padding:0;">
                <div class="form-group">
                    <label for="systemName">System Name:</label>
                    <input type="text" id="systemName" class="form-control" required>
                </div>
                <div class="form-group">
                    <label for="systemDescription">Description:</label>
                    <textarea id="systemDescription" class="form-control"></textarea>
                </div>
                <div class="form-group">
                    <label for="systemStatus">Status:</label>
                    <select id="systemStatus" class="form-control">
                        {% for choice_value, choice_label in pyview.status_choices %}
                            <option value="{{ choice_value }}">{{ choice_label }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-group">
                    <label for="systemOs">OS:</label>
                    <select id="systemOs" class="form-control">
                        {% for choice_value, choice_label in pyview.os_choices %}
                            <option value="{{ choice_value }}">{{ choice_label }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-group">
                    <label for="systemConnectionMode">Connection Mode:</label>
                    <select id="systemConnectionMode" class="form-control">
                        {% for choice_value, choice_label in pyview.connection_mode_choices %}
                            <option value="{{ choice_value }}">{{ choice_label }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-group">
                    <label for="systemExecutorUrl">Executor URL:</label>
                    <input type="url" id="systemExecutorUrl" class="form-control" placeholder="http://1.2.3.4:8000">
                </div>
                <div class="form-group">
                    <label for="systemExecutorApiKey">Executor API Key:</label>
                    <input type="text" id="systemExecutorApiKey" class="form-control">
                </div>
            </div>
            <div class="modal-footer" style="padding:0; border:0; margin-top: 15px; text-align: right;">
                <button class="btn btn-secondary" onclick="pyview.toggle_add_system()">Cancel</button>
                <button id="saveSystemBtn" class="btn btn-primary" onclick="pyview.save_system(
                    document.getElementById('systemName').value,
                    document.getElementById('systemDescription').value,
                    document.getElementById('systemStatus').value,
                    document.getElementById('systemOs').value,
                    document.getElementById('systemConnectionMode').value,
                    document.getElementById('systemExecutorUrl').value,
                    document.getElementById('systemExecutorApiKey').value
                )">Save System</button>
            </div>
        </div>
        {% endif %}

        <div id="systems-list-body" class="sidebar-list-body" style="padding-top: 10px;">
            {% if pyview.system_views %}
                {% for sview in pyview.system_views %}
                    {{ sview.render() }}
                {% endfor %}
            {% else %}
                 <p style="padding: 40px; text-align: center; color: #999; font-style: italic;">No systems configured yet.</p>
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
        self.systems = list(System.objects.all())
        self.system_views = [SystemListItemView(s, self) for s in self.systems]

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
                name=name,
                description=description,
                status=status,
                os=os,
                executor_mode=executor_mode,
                executor_url=executor_url,
                executor_api_key=executor_api_key
            )
            self.show_add_form = False
            self.update()
