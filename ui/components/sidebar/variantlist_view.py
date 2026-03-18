from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView

class SidebarVariantListView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="sidebar-list-body">
        <ul class="tree-view-list">
            {% for pk, variant_view in pyview.variant_views.items() %}
                {{ variant_view.render() }}
            {% endfor %}
        </ul>
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app = parent.app
        self._subject = subject
        self._fooar = subject
        self.variant_views = {}
        self._rebuild_variant_views()

    def _rebuild_variant_views(self):
        from ui.components.sidebar.variantnode_view import SidebarVariantNodeView
        self.variant_views = {}
        self.variant_views[self.subject.profile.id] = SidebarVariantNodeView(self.subject.profile, self)
        self.update()

    def _on_subject_updated(self, source, **kwargs):
        self._rebuild_variant_views()

