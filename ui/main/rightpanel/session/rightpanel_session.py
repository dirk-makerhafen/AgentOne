           

from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from server.models.workspace import WorkspaceModel
from ui.lib.model_view import ModelView
from ui.main.rightpanel.session.rightpanel_session_calls import RightPanelSessionCalls
from ui.main.rightpanel.session.rightpanel_session_settings import RightPanelSessionSettings
from ui.main.rightpanel.session.rightpanel_session_subagents import RightPanelSessionSubagents
from ui.main.rightpanel.session.rightpanel_session_tasks import RightPanelSessionTasks
from ui.main.rightpanel.session.rightpanel_session_todos import RightPanelSessionTodos
from ui.main.rightpanel.workspace.rightpanel_workspace_files import RightPanelWorkspaceFiles

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp



class RightPanelSession(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="sidebar-nav">
            <button class="nav-tab{% if pyview.current_tab_name == "workspace" %} active{% endif %}" data-panel="workspace" data-label="Workspace" onclick="pyview.switchTab('workspace')" title="Workspace">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "settings" %} active{% endif %}" data-panel="settings" data-label="Settings" onclick="pyview.switchTab('settings')" title="Settings">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "tasks" %} active{% endif %}" data-panel="tasks" data-label="Capabilities" onclick="pyview.switchTab('tasks')" title="Capabilities">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "todos" %} active{% endif %}" data-panel="todos" data-label="Todos" onclick="pyview.switchTab('todos')" title="Todos">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "calls" %} active{% endif %}" data-panel="calls" data-label="Calls" onclick="pyview.switchTab('calls')" title="Calls">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "subagents" %} active{% endif %}" data-panel="subagents" data-label="Subagents" onclick="pyview.switchTab('subagents')" title="Subagents">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>
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

    def __init__(self, subject: SessionModel, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.current_tab_name = None
        self.current_tab = None
        self.session = Session(session_model=subject)


    def switchTab(self, name: str) -> None:
        if name == self.current_tab_name:
            return 
        if name not in ["workspace", "settings", "tasks", "todos", "calls", "subagents"]:
            return
        self.current_tab_name = name
        if self.current_tab:
            self.current_tab.delete(remove_from_dom=False)
        if name == "workspace":
            workspace: WorkspaceModel = self.session.workspace
            if not workspace:
                return None
            self.current_tab = RightPanelWorkspaceFiles(workspace, self)
        elif name == "settings":
            self.current_tab = RightPanelSessionSettings(self.subject, self)
        elif name == "tasks":
            self.current_tab = RightPanelSessionTasks(self.subject, self)
        elif name == "todos":
            self.current_tab = RightPanelSessionTodos(self.subject, self)
        elif name == "calls":
            self.current_tab = RightPanelSessionCalls(self.subject, self)
        elif name == "subagents":
            self.current_tab = RightPanelSessionSubagents(self.subject, self)
        self.update()

