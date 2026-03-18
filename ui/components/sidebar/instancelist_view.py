from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView
from ui.components.sidebar.instancenode_view import SidebarInstanceNodeView

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ui.main_view import UiAppView

class SidebarInstanceListView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="sidebar-list-body">
        <ul class="tree-view-list">
        {{pyview.ninstance_views.render()}}
            {% for pk, instanceview in pyview.instance_views.items() %}
                {{ instanceview.render() }}
            {% endfor %}
        </ul>
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app = parent.app
        self.app:UiAppView
        self.s = subject

        self.ninstance_views = QuerySetView(subject=subject.agent_instances.filter(parent=None), parent=self, item_class=SidebarInstanceNodeView)

        self.instance_views = {}
        #self._rebuild_instance_views()

    def _rebuild_instance_views(self):
        return
        # Clear existing views and create new ones based on the current list of instances
        self.instance_views = {}
        print(" self.subject self.subject",  self.subject)
        self.instances = self.subject.agent_instances.filter(parent=None) # Assuming subject.instances.all() is a QuerySet
        for instance in self.instances:
            self.instance_views[instance.id] = SidebarInstanceNodeView(instance, self)
        self.update()

    def _on_subject_updated(self, source, **kwargs):
        self._rebuild_instance_views()

