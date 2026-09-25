from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView
from ui.main.rightpanel.workspace.rightpanel_workspace_files import RightPanelWorkspaceFiles
from ui.main.rightpanel.workspace.rightpanel_workspace_manager import RightPanelWorkspaceManager
from ui.main.rightpanel.workspace.rightpanel_workspace_usage import RightPanelWorkspaceUsage

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from server.models.workspace import WorkspaceModel


class RightPanelWorkspace(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="sidebar-nav">
            <button class="nav-tab{% if pyview.current_tab_name == "files" %} active{% endif %}" data-panel="files" data-label="Files" onclick="pyview.switchTab('files')" title="Files">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "usage" %} active{% endif %}" data-panel="usage" data-label="Usage" onclick="pyview.switchTab('usage')" title="Usage">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "manager" %} active{% endif %}" data-panel="manager" data-label="Manager" onclick="pyview.switchTab('manager')" title="Workspace Manager">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
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

    def __init__(self, subject: WorkspaceModel, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.current_tab_name = None
        self.current_tab = None

    def switchTab(self, name: str) -> None:
        if name == self.current_tab_name:
            return 
        if name not in ["files", "usage", "manager"]:
            return
        self.current_tab_name = name
        if self.current_tab:
            self.current_tab.delete(remove_from_dom=False)
        if name == "files":
            self.current_tab = RightPanelWorkspaceFiles(self.subject, self)
        elif name == "usage":
            self.current_tab = RightPanelWorkspaceUsage(self.subject, self)
        elif name == "manager":
            self.current_tab = RightPanelWorkspaceManager(self.subject, self)
        self.update()

