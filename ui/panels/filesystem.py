from server.models.agents.agent_instance_version import AgentInstanceVersion
from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.components.filesystem.filesystemheader_view import FilesystemHeaderView
from ui.components.filesystem.filesystemitem_view import FilesystemItemView

class FilesystemView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="section">
        <div id="filesystem-header-container_{{ pyview.subject.id }}">
            {% if pyview.subject.header %}{{ pyview.render_header() }}{% endif %}
        </div>
        
        <div class="fs-list-header" id="fs-list-header_{{ pyview.subject.id }}">
            <span class="sort-header-item" data-sort-column="path" onclick="pyview.handle_filesystem_sort('path')">Name <i class="fa fa-sort"></i></span>
            <span class="sort-header-item" data-sort-column="size" onclick="pyview.handle_filesystem_sort('size')">Size <i class="fa fa-sort"></i></span>
            <span class="sort-header-item sort-header-actions" data-sort-column="actions" onclick="pyview.handle_filesystem_sort('actions')">Actions <i class="fa fa-sort"></i></span>
        </div>

        <div id="filesystem-list_{{ pyview.subject.id }}" class="fs-list">
            {% for item in pyview.subject.get_loaded_items() %}
                {{ pyview.render_item(item) }}
            {% endfor %}
        </div>
        <div class="fs-input-container">
            <textarea id="fs-path-input_{{ pyview.subject.id }}" rows="3" placeholder="Enter one path per line..."></textarea>
            <button id="fs-load-btn_{{ pyview.subject.id }}" class="button" onclick="pyview.sidebar_fs_load(document.getElementById('fs-path-input_{{pyview.subject.id}}').value)">Load</button>
        </div>
        <div class="fs-rules-container">
            <i class="fa fa-question-circle fs-rules-help" title="Access Rules Syntax:\n- Deny: !path/to/deny\n- Allow Write: >path/to/allow\n- Read-only: <path/to/file\nRules are checked in order. Wildcards (*) are supported. Default is deny."></i>
            <textarea id="fs-access-rules_{{ pyview.subject.id }}" class="fs-rules-textarea" placeholder="Access Rules (!/denied, >/writeok, </readonly)" onblur="pyview.save_sidebar_fs_permission('access_rules', this.value)">{{ pyview.subject.access_rules }}</textarea>
        </div>
        {{pyview.s}}
    </div>
    """
    def __init__(self, subject: AgentInstanceVersion, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject
        self._header_view = None
        self._item_views = {}

    def render_header(self):
        if not self._header_view:
            self._header_view = FilesystemHeaderView(self.subject, self)
        return self._header_view.render()

    def render_item(self, item):
        if item.id not in self._item_views:
            self._item_views[item.id] = FilesystemItemView(subject=item, parent=self)
        return self._item_views[item.id].render()

    def handle_filesystem_sort(self, column):
        #todo 
        self.update()

    def sidebar_fs_load(self, paths_str):
        paths = [p.strip() for p in paths_str.split('\n') if p.strip()]
        print("self.subject", self.subject, type(self.subject))
        for path in paths:
            self.subject.fs_load.delay(path=path)

        # In a real scenario, this would trigger backend logic to load these files
        print(f"Loading paths: {paths}")
        # For now, just clear the input and update
        self.update()

    def save_sidebar_fs_permission(self, rule_type, value):
        #if rule_type == 'access_rules':
        #    self.subject.access_rules = value
        # Add other rule types as needed
        #self.subject.save()
        #self.update()
        pass
        print("todo")


from server.models.agents.agent_instance_version import AgentInstanceVersion
from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

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



from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry

class FilesystemItemView(PyHtmlView):
    TEMPLATE_STR = """
    <div id="fs-item-{{ pyview.subject.id }}" class="fs-item {% if not pyview.subject.is_loaded %}fs-item-unloaded{% endif %}" data-path="{{ pyview.subject.path }}" data-timestamp="{{ pyview.subject.created_at }}" data-is-loaded="{{ pyview.subject.is_loaded }}" data-instance-pk="{{ pyview.instancePk }}" data-load-mode="{{ pyview.subject.load_mode }}">
        <i class="fa {% if pyview.subject.is_dir %}fa-folder-o{% else %}{% if pyview.subject.is_summary %}fa-file{% else %}fa-file-o{% endif %}{% endif %} item-icon"></i>
        
        <span class="fs-path item-text" title="{{ pyview.subject.path }}">{{ pyview.subject.path }}</span>
        <span class="fs-token-count">{{ pyview.subject.tokens }}</span>
        {% if pyview.subject.deleted %}<span class="item-deleted" title="File no longer exists"><i class="fa fa-exclamation-circle"></i></span>{% endif %}
        <div class="item-actions">
            <i class="fa fa-thumb-tack fs-pin-btn {% if pyview.subject.is_pinned %}pinned{% endif %}" 
               data-fslogentry-pk="{{ pyview.subject.id }}"
               data-is-pinned="{{ pyview.subject.is_pinned }}"
               onclick="pyview.fs_pin()"
               title="{% if pyview.subject.is_pinned %}Unpin this item{% else %}Pin this item{% endif %}"></i>
            {% if not pyview.subject.is_dir %}
                {% if pyview.subject.is_loaded %}
                    {% if pyview.subject.is_summary %}
                        <i class="fa fa-expand fs-toggle-load-mode-btn" data-path="{{ pyview.subject.path }}" data-id="{{ pyview.subject.id }}" data-load-mode="summary" onclick="pyview.fs_toggle_load_mode()" title="Switch to Full Load Mode"></i>
                    {% else %}
                        <i class="fa fa-compress fs-toggle-load-mode-btn" data-path="{{ pyview.subject.path }}"data-id="{{ pyview.subject.id }}"  data-load-mode="full" onclick="pyview.fs_toggle_load_mode()" title="Switch to Summary Load Mode"></i>
                    {% endif %}
                {% endif %}
            {% endif %}
            <i class="fa fa-sign-out fs-unload-btn" data-path="{{ pyview.subject.path }}" data-path="{{ pyview.subject.id }}" onclick="pyview.fs_unload()" title="Unload this item" style="{% if not pyview.subject.is_loaded %}display: none;{% endif %}"></i>
            <i class="fa fa-sign-in fs-load-btn" data-path="{{ pyview.subject.path }}"    data-path="{{ pyview.subject.id }}" onclick="pyview.fs_load_item()" title="Load this item" style="{% if pyview.subject.is_loaded %}display: none;{% endif %}"></i>
        </div>
    </div>
    """
    def __init__(self, subject:FsLogEntry, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject

    def fs_pin(self):
        self.subject.is_pinned = not self.subject.is_pinned
        self.subject.save()
        self.update()
    def fs_toggle_load_mode(self):
        # Toggle between 'full' and 'summary'
        self.subject.load_mode = 'summary' if self.subject.load_mode == 'full' else 'full'
        self.subject.save()
        self.update()
    def fs_unload(self):
        # This should mark the item as unloaded in the backend
        self.subject.is_loaded = False
        self.subject.save()
        self.update()
    def fs_load_item(self):
        # This should mark the item as loaded in the backend
        self.subject.is_loaded = True
        self.subject.save()
        self.update()

