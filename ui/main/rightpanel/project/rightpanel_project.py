from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.project import Project
from ui.lib.model_view import ModelView
from ui.main.rightpanel.project.rightpanel_project_overview import RightPanelProjectOverview
from ui.main.rightpanel.project.rightpanel_project_workspaces import RightPanelProjectWorkspaces

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


class RightPanelProject(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="sidebar-nav">
            <button class="nav-tab{% if pyview.current_tab_name == "overview" %} active{% endif %}" data-panel="overview" data-label="Overview" onclick="pyview.switchTab('overview')" title="Overview">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "workspaces" %} active{% endif %}" data-panel="workspaces" data-label="Workspaces" onclick="pyview.switchTab('workspaces')" title="Workspaces">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            </button>

        </div>
        {% if pyview.current_tab %}
            {{ pyview.current_tab.render() }}
        {% else %}
            <div style="flex:1;padding:8px">
                <div style="font-size:12px;color:var(--muted);text-align:center;margin-top:40%"></div>
            </div>
        {% endif %}
        <div class="resize-handle" id="rightpanelResize"></div>
    '''

    def __init__(self, subject: Project, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.current_tab_name = None
        self.current_tab = None

    def switchTab(self, name: str) -> None:
        if name == self.current_tab_name:
            return 
        if name not in ["overview", "workspaces"]:
            return
        self.current_tab_name = name
        if self.current_tab:
            self.current_tab.delete(remove_from_dom=False)
        if name == "overview":
            self.current_tab = RightPanelProjectOverview(self.subject, self)
        elif name == "workspaces":
            self.current_tab = RightPanelProjectWorkspaces(self.subject, self)
        self.update()
