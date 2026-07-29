from __future__ import annotations
from typing import TYPE_CHECKING

from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from server.models.agents.agent import AgentModel
from server.models.collections import DataCollection
from server.models.cron import Cronjob
from server.models.project import Project
from server.models.workspace import WorkspaceModel
from server.models.skills.skill import SkillModel
from ui.lib.model_view import ModelView
from ui.main.rightpanel.session import RightPanelSession
from ui.main.rightpanel.tasks import RightPanelTasks
from ui.main.rightpanel.calls import RightPanelCalls
from ui.main.rightpanel.workspace import RightPanelWorkspace
from ui.main.rightpanel.subagents import RightPanelSubagents
from ui.main.rightpanel.cron import RightPanelCronSchedule, RightPanelCronHistory, CRON_ICONS
from ui.main.rightpanel.collection import RightPanelCollectionActivity, RightPanelCollectionDerived, FLOW_ICONS
from ui.main.rightpanel.agent import RightPanelAgentInfo, RightPanelAgentSessions, RightPanelAgentCapabilities, AGENT_ICONS
from ui.main.rightpanel.project import RightPanelProjectOverview, RightPanelProjectWorkspaces, PROJECT_ICONS
from ui.main.rightpanel.workspace_context import RightPanelWorkspaceUsage, WORKSPACE_ICONS
from ui.main.rightpanel.skill import RightPanelSkillInfo, RightPanelSkillAgents, SKILL_ICONS

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.app_view import UiAppView
    from ui.main.main_view import MainView
    from ui.main.chat.chat import Chat
    from ui.main.cron.cron import CronView
    from ui.main.collections.collection_detail import CollectionDetailView
    from ui.main.agent.agent_view import AgentView
    from ui.main.project.project_view import ProjectView
    from ui.main.workspace.workspace import Workspace as WorkspaceView
    from ui.main.skills.skill_view import SkillView


TAB_ICONS = {
    "schedule": CRON_ICONS["schedule"],
    "history": CRON_ICONS["history"],
    "activity": FLOW_ICONS["activity"],
    "derived": FLOW_ICONS["derived"],
    "info": AGENT_ICONS["info"],
    "sessions": AGENT_ICONS["sessions"],
    "capabilities": AGENT_ICONS["capabilities"],
    "overview": PROJECT_ICONS["overview"],
    "workspaces": PROJECT_ICONS["workspaces"],
    "files": WORKSPACE_ICONS["files"],
    "usage": WORKSPACE_ICONS["usage"],
    "agents": SKILL_ICONS["agents"],
}

ICON_MAP = {
    "workspace": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
    "session": '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    "tasks": '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
    "subagents": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>',
    "calls": '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
}


class RightPanel(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        {% if pyview.tabs %}
        <div class="sidebar-nav">
            {% for tab in pyview.tabs %}
            <button class="nav-tab{% if tab.active %} active{% endif %}" data-panel="{{ tab.name }}" data-label="{{ tab.label }}" onclick="pyview.switchPanel('{{ tab.name }}')" title="{{ tab.label }}">
                {{ tab.icon|safe }}
            </button>
            {% endfor %}
        </div>
        <div class="resize-handle" id="rightpanelResize"></div>
        {% endif %}
        {% if pyview.current_view %}
        {{ pyview.current_view.render() }}
        {% else %}
        <div style="flex:1;padding:8px">
            <div style="font-size:12px;color:var(--muted);text-align:center;margin-top:40%"></div>
        </div>
        {% endif %}
    '''

    # Session tabs (reuse existing views)
    SESSION_TABS = [
        ("workspace", "Workspace", "workspace"),
        ("session", "Session", "session"),
        ("tasks", "Capabilities", "tasks"),
        ("calls", "Calls", "calls"),
        ("subagents", "Sub-agents", "subagents"),
    ]

    def __init__(self, subject: UiApp, parent: UiAppView, **kwargs):
        super().__init__(subject, parent, **kwargs)

        self.workspace_view = RightPanelWorkspace(subject, self)
        self.session_view = RightPanelSession(subject, self)
        self.subagents_view = RightPanelSubagents(subject, self)
        self.tasks_view = RightPanelTasks(subject, self)
        self.calls_view = RightPanelCalls(subject, self)

        # Non-session tab views (lazy-created by context handlers)
        self._cron_schedule: RightPanelCronSchedule | None = None
        self._cron_history: RightPanelCronHistory | None = None
        self._collection_activity: RightPanelCollectionActivity | None = None
        self._collection_derived: RightPanelCollectionDerived | None = None
        self._agent_info: RightPanelAgentInfo | None = None
        self._agent_sessions: RightPanelAgentSessions | None = None
        self._agent_capabilities: RightPanelAgentCapabilities | None = None
        self._project_overview: RightPanelProjectOverview | None = None
        self._project_workspaces: RightPanelProjectWorkspaces | None = None
        self._workspace_files: RightPanelWorkspace | None = None
        self._workspace_usage: RightPanelWorkspaceUsage | None = None
        self._skill_info: RightPanelSkillInfo | None = None
        self._skill_agents: RightPanelSkillAgents | None = None

        self._tabs: list[dict] = []
        self._tab_map: dict[str, ModelView] = {}
        self.current_view: ModelView | None = None
        self._current_tab_name: str = ""
        self._update_context()

    # ------------------------------------------------------------------
    # Properties accessed by template
    # ------------------------------------------------------------------

    @property
    def tabs(self) -> list[dict]:
        return self._tabs

    @property
    def main_panel(self) -> MainView:
        return self.parent.main_panel

    @property
    def current_subject(self):
        """The model instance currently shown in the main panel."""
        tab = self.main_panel.selected_tab_view
        if tab is not None and hasattr(tab, "subject"):
            return tab.subject
        return None

    @property
    def current_session(self) -> Session | None:
        tab = self.main_panel.selected_tab_view
        if tab is not None and hasattr(tab, "session"):
            subj = tab.session
            if isinstance(subj, Session):
                return subj
        return None

    # ------------------------------------------------------------------
    # Context dispatch (called by MainView after tab switch)
    # ------------------------------------------------------------------

    def _update_context(self) -> None:
        tab = self.main_panel.selected_tab_view
        if tab is None:
            self._show_empty_context()
            self.update()
            return

        from ui.main.chat.chat import Chat
        from ui.main.cron.cron import CronView
        from ui.main.collections.collection_detail import CollectionDetailView
        from ui.main.agent.agent_view import AgentView
        from ui.main.project.project_view import ProjectView
        from ui.main.workspace.workspace import Workspace as WorkspaceView
        from ui.main.skills.skill_view import SkillView

        if isinstance(tab, Chat):
            self._show_session_context()
        elif isinstance(tab, CronView):
            self._show_cron_context()
        elif isinstance(tab, CollectionDetailView):
            self._show_collection_context()
        elif isinstance(tab, AgentView):
            self._show_agent_context()
        elif isinstance(tab, ProjectView):
            self._show_project_context()
        elif isinstance(tab, WorkspaceView):
            self._show_workspace_context()
        elif isinstance(tab, SkillView):
            self._show_skill_context()
        else:
            self._show_empty_context()
        self.update()

    # ------------------------------------------------------------------
    # Context handlers
    # ------------------------------------------------------------------

    def _show_empty_context(self) -> None:
        self._tabs = []
        self._tab_map = {}
        self.current_view = None

    def _show_session_context(self) -> None:
        self._tabs = [
            {
                "name": n,
                "label": l,
                "icon": ICON_MAP.get(n, ""),
                "active": self._current_tab_name == n or (self._current_tab_name == "" and i == 0),
            }
            for i, (n, l, _) in enumerate(self.SESSION_TABS)
        ]
        self._tab_map = {n: v for n, _, v in [
            ("workspace", "", self.workspace_view),
            ("session", "", self.session_view),
            ("tasks", "", self.tasks_view),
            ("calls", "", self.calls_view),
            ("subagents", "", self.subagents_view),
        ]}
        if self._current_tab_name not in self._tab_map:
            self._current_tab_name = "workspace"
        self.current_view = self._tab_map.get(self._current_tab_name, self.workspace_view)
        self.subagents_view.refresh()

    def _show_cron_context(self) -> None:
        if self._cron_schedule is None:
            self._cron_schedule = RightPanelCronSchedule(self.subject, self)
        if self._cron_history is None:
            self._cron_history = RightPanelCronHistory(self.subject, self)
        self._set_tabs([
            ("schedule", "Schedule", self._cron_schedule),
            ("history", "History", self._cron_history),
        ])

    def _show_collection_context(self) -> None:
        if self._collection_activity is None:
            self._collection_activity = RightPanelCollectionActivity(self.subject, self)
        if self._collection_derived is None:
            self._collection_derived = RightPanelCollectionDerived(self.subject, self)
        self._set_tabs([
            ("activity", "Activity", self._collection_activity),
            ("derived", "Derived", self._collection_derived),
        ])

    def _show_agent_context(self) -> None:
        if self._agent_info is None:
            self._agent_info = RightPanelAgentInfo(self.subject, self)
        if self._agent_sessions is None:
            self._agent_sessions = RightPanelAgentSessions(self.subject, self)
        if self._agent_capabilities is None:
            self._agent_capabilities = RightPanelAgentCapabilities(self.subject, self)
        self._set_tabs([
            ("info", "Info", self._agent_info),
            ("sessions", "Sessions", self._agent_sessions),
            ("capabilities", "Capabilities", self._agent_capabilities),
        ])

    def _show_project_context(self) -> None:
        if self._project_overview is None:
            self._project_overview = RightPanelProjectOverview(self.subject, self)
        if self._project_workspaces is None:
            self._project_workspaces = RightPanelProjectWorkspaces(self.subject, self)
        self._set_tabs([
            ("overview", "Overview", self._project_overview),
            ("workspaces", "Workspaces", self._project_workspaces),
        ])

    def _show_workspace_context(self) -> None:
        if self._workspace_files is None:
            self._workspace_files = RightPanelWorkspace(self.subject, self)
        if self._workspace_usage is None:
            self._workspace_usage = RightPanelWorkspaceUsage(self.subject, self)
        self._set_tabs([
            ("files", "Files", self._workspace_files),
            ("usage", "Usage", self._workspace_usage),
        ])

    def _show_skill_context(self) -> None:
        if self._skill_info is None:
            self._skill_info = RightPanelSkillInfo(self.subject, self)
        if self._skill_agents is None:
            self._skill_agents = RightPanelSkillAgents(self.subject, self)
        self._set_tabs([
            ("info", "Info", self._skill_info),
            ("agents", "Agents", self._skill_agents),
        ])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_tabs(self, tab_defs: list[tuple[str, str, ModelView]]) -> None:
        """Install a list of (name, label, view) tuples as the current tab set."""
        self._tabs = []
        self._tab_map = {}
        for name, label, view in tab_defs:
            self._tab_map[name] = view
            icon = TAB_ICONS.get(name, "")
            active = self._current_tab_name == name
            self._tabs.append({"name": name, "label": label, "icon": icon, "active": active})
        if self._current_tab_name not in self._tab_map:
            self._current_tab_name = tab_defs[0][0] if tab_defs else ""
            if self._tabs:
                self._tabs[0]["active"] = True
        self.current_view = self._tab_map.get(self._current_tab_name)

    def switchPanel(self, name: str) -> None:
        view = self._tab_map.get(name)
        if view is not None and view != self.current_view:
            self.current_view = view
            self._current_tab_name = name
            for tab in self._tabs:
                tab["active"] = tab["name"] == name
            if name == "subagents":
                self.subagents_view.refresh()
            if name == "tasks":
                self.tasks_view.refresh()
            if name == "calls":
                self.calls_view.refresh()
            self.update()

    def update(self, *args, **kwargs) -> None:
        super().update(*args, **kwargs)
