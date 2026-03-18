from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView

class SidebarVersionListView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="sidebar-list-body" style="display:none">
        <ul class="tree-view-list">
            {% for pk, versionview in pyview.version_views.items() %}
                { { versionview.render() } }
            {% endfor %}
        </ul>
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app = parent.app
        self._subject = subject
        self._fooar = subject
        self.version_views = {}
        self._rebuild_version_views()

    def _rebuild_version_views(self):
        from ui.components.sidebar.versionnode_view import SidebarVersionNodeView
        self.version_views = {}
        self.agent_versions = self.subject.agent_versions.all() # Assuming subject.agent_versions.all() is a QuerySet
        for agent_version in self.agent_versions:
            self.version_views[agent_version.id] = SidebarVersionNodeView(agent_version, self)
        self.update()

    def _on_subject_updated(self, source, **kwargs):
        self._rebuild_version_views()

