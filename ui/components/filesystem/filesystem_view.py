from server.models.agents.agent_instance_version import AgentInstanceVersion
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
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