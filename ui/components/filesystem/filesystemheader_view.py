from server.models.agents.agent_instance_version import AgentInstanceVersion
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView

class FilesystemHeaderView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="fs-header-new">
        <div id="workingdir-display_{{ pyview.subject.id }}" class="fs-header-item">
            {% if pyview.subject.workingdir %}
            <span id="workingdir-text_{{ pyview.subject.id }}" class="editable-path" onclick="pyview.show_workingdir_edit()" title="{{ pyview.subject.workingdir }}">{{ pyview.subject.workingdir }}</span>
        {% else %}
            <span id="workingdir-text_{{ pyview.subject.id }}" class="editable-path placeholder" onclick="pyview.show_workingdir_edit()" title="Click to set working directory" style="font-style: italic; color: #999;">[Not Set]</span>
        {% endif %}
        </div>
        <div id="workingdir-edit_{{ pyview.subject.id }}" class="fs-header-item" style="{% if pyview.is_edit_mode %}display: block;{% else %}display: none;{% endif %} width: -webkit-fill-available;">
            <input type="text" id="workingdir-input_{{ pyview.subject.id }}" value="{{ pyview.subject.workingdir }}" onkeydown="pyview.handle_workingdir_keydown(event)" />
            <i class="fa fa-check" onclick="pyview.save_workingdir()"></i>
            <i class="fa fa-times" onclick="pyview.cancel_workingdir_edit()"></i>
        </div>
        <div class="fs-header-item fs-token-count"><span id="total-fs-tokens_{{ pyview.subject.id }}">{{ pyview.subject.total_fs_tokens }}</span></div>
        <div class="fs-header-controls">
            <i id="fs-view-toggle_{{ pyview.subject.id }}" class="fa fa-eye fs-view-toggle" title="Toggle visibility of unloaded items" onclick="pyview.fs_toggle_view()"></i>
            <i id="fs-write-permission-toggle_{{ pyview.subject.id }}" 
            class="fa {% if pyview.subject.workingdir_write_allowed %}fa-pencil unlocked{% else %}fa-pencil locked{% endif %} fs-permission-toggle" 
            title="{% if pyview.subject.workingdir_write_allowed %}WD Write: ON{% else %}WD Write: OFF{% endif %}"
            onclick="pyview.save_fs_permission('workingdir_write_allowed', {% if pyview.subject.workingdir_write_allowed %}false{% else %}true{% endif %})"></i>
        </div>
    </div>
    """
    def __init__(self, subject:AgentInstanceVersion, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject
        self.is_edit_mode = False

    def show_workingdir_edit(self): 
        self.is_edit_mode = True
        self.update()

    def handle_workingdir_keydown(self, event):
        if event.key == 'Enter':
            self.save_workingdir()
        elif event.key == 'Escape':
            self.cancel_workingdir_edit()
    def save_workingdir(self):
        new_path = self.eval_javascript(script=f"return document.getElementById('workingdir-input_{self.subject.id}').value;")
        if self.subject.workingdir != new_path:
            self.subject.workingdir = new_path
            self.subject.save()
        self.is_edit_mode = False
        self.update()

    def cancel_workingdir_edit(self): 
        self.is_edit_mode = False
        self.update()

    def fs_toggle_view(self):
        self.subject.show_unloaded_items = not self.subject.show_unloaded_items
        self.subject.save()
        self.update()
        
    def save_fs_permission(self, permission_type, value):
        # This will need to interact with a permissions model or a dedicated field on the instance
        print(f"Setting permission {permission_type} to {value}")
        if permission_type == 'workingdir_write_allowed':
            self.subject.workingdir_write_allowed = value
        # Add other permission types as needed
        self.subject.save()
        self.update()

