           

from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from server.models.workspace import WorkspaceModel
from ui.lib.model_view import ModelView
from ui.main.rightpanel.session.rightpanel_session_calls import RightPanelSessionCalls
from ui.main.rightpanel.session.rightpanel_session_settings import RightPanelSessionSettings
from ui.main.rightpanel.session.rightpanel_session_subagents import RightPanelSessionSubagents
from ui.main.rightpanel.session.rightpanel_session_terminal import RightPanelSessionTerminals
from ui.main.rightpanel.session.rightpanel_session_tasks import RightPanelSessionTasks
from ui.main.rightpanel.session.rightpanel_session_templates import RightPanelSessionTemplates
from ui.main.rightpanel.session.rightpanel_session_todos import RightPanelSessionTodos
from ui.main.rightpanel.workspace.rightpanel_workspace_files import RightPanelWorkspaceFiles

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp



class RightPanelSession(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        {% if pyview.has_agent_update %}
        <div style="margin:8px;padding:8px;border:1px solid var(--warning, #b7791f);border-radius:6px;background:var(--warning-bg, rgba(183,121,31,0.12));font-size:12px">
            <div style="font-weight:600;margin-bottom:4px">New agent version available (v{{ pyview.pinned_agent_version_number }} → v{{ pyview.latest_agent_version_number }})</div>
            <div style="color:var(--muted);margin-bottom:6px">This chat stays pinned to v{{ pyview.pinned_agent_version_number }} to keep the prompt cache hot. New chats and compactions use the latest tools/prompts.</div>
            <button type="button" onclick="pyview.upgradeAgentVersion()" style="font-size:12px;padding:4px 10px;cursor:pointer">Use latest now</button>
        </div>
        {% endif %}
        <div class="sidebar-nav">
            <button class="nav-tab{% if pyview.current_tab_name == "workspace" %} active{% endif %}" data-panel="workspace" data-label="Workspace" onclick="pyview.switchTab('workspace')" title="Workspace">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "settings" %} active{% endif %}" data-panel="settings" data-label="Settings" onclick="pyview.switchTab('settings')" title="Settings">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "templates" %} active{% endif %}" data-panel="templates" data-label="Templates" onclick="pyview.switchTab('templates')" title="Templates">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="13" y2="17"/></svg>
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
            <button class="nav-tab{% if pyview.current_tab_name == "terminal" %} active{% endif %}" data-panel="terminal" data-label="Terminals" onclick="pyview.switchTab('terminal')" title="Terminals">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
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

    @property
    def has_agent_update(self) -> bool:
        try:
            self.subject.refresh_from_db(fields=["latest_session_version"])
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            return Session(session_model=self.subject).has_agent_update()
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    @property
    def pinned_agent_version_number(self) -> str:
        try:
            pinned = Session(session_model=self.subject).pinned_agent_version
            return str(pinned.version_number) if pinned is not None else "?"
        except Exception:  # pylint: disable=broad-exception-caught
            return "?"

    @property
    def latest_agent_version_number(self) -> str:
        try:
            latest = Session(session_model=self.subject).latest_agent_version
            return str(latest.version_number) if latest is not None else "?"
        except Exception:  # pylint: disable=broad-exception-caught
            return "?"

    def upgradeAgentVersion(self) -> None:
        """Pin this session to the latest agent/tools version now.

        Takes effect on the next turn (fresh KV-cache prefix); the current
        history is preserved.
        """
        try:
            sess = Session(session_model=self.subject)
            if sess.upgrade_to_latest_agent():
                self.subject.refresh_from_db(fields=["latest_session_version"])
                self.session = Session(session_model=self.subject)
                # Rebuild the active tab so capability lists reflect the new
                # tool set immediately.
                if self.current_tab_name:
                    name = self.current_tab_name
                    self.current_tab_name = None
                    self.switchTab(name)
                    return
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        self.update()


    def switchTab(self, name: str) -> None:
        if name == self.current_tab_name:
            return 
        if name not in ["workspace", "settings", "tasks", "templates", "todos", "calls", "subagents", "terminal"]:
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
        elif name == "templates":
            self.current_tab = RightPanelSessionTemplates(self.subject, self)
        elif name == "todos":
            self.current_tab = RightPanelSessionTodos(self.subject, self)
        elif name == "calls":
            self.current_tab = RightPanelSessionCalls(self.subject, self)
        elif name == "subagents":
            self.current_tab = RightPanelSessionSubagents(self.subject, self)
        elif name == "terminal":
            self.current_tab = RightPanelSessionTerminals(self.subject, self)
        self.update()

