from __future__ import annotations
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ui.main_view import UiApp
    from ui.main_view import UiAppView

class SidebarAgentListView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="sidebar-list-body">
        <ul class="tree-view-list">
            {% for pk, agentview in pyview.agent_views.items() %}
                {{ agentview.render() }}
            {% endfor %}
        </ul>
    </div>
    """
    def __init__(self, subject:UiApp, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.app = parent.app
        self.app:UiAppView
        
        self.agent_views = {}
        self._rebuild_agent_views()

    def _rebuild_agent_views(self):
        from ui.components.sidebar.agentnode_view import SidebarAgentNodeView

        # Clear existing views and create new ones based on the current list of agents
        self.agent_views = {}
        self.agents = self.subject.agents.all() # Assuming subject.agents.all() is a QuerySet
        for agent in self.agents:
            self.agent_views[agent.id] = SidebarAgentNodeView(agent, self)
        self.update()

    def _on_subject_updated(self, source, **kwargs):
        self._rebuild_agent_views()
