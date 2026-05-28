from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.rightpanel.session import RightPanelSession
from ui.main.rightpanel.tasks import RightPanelTasks
from ui.main.rightpanel.workspace import RightPanelWorkspace
from ui.main.rightpanel.subagents import RightPanelSubagents


if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.app_view import UiAppView
    from ui.main.main_view import MainView

class RightPanel(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        <div class="sidebar-nav">
            <button class="nav-tab active" data-panel="workspace" data-label="Workspace" onclick="pyview.switchPanel('workspace')" title="Workspace" data-i18n-title="tab_workspace">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                <div class="rail-button-text" style="display:none">Workspace</div>
            </button>
            <button class="nav-tab active" data-panel="session" data-label="Session" onclick="pyview.switchPanel('session')" title="Session" data-i18n-title="tab_session">
                 <!-- AI TODO: better "session" icon, not this reused gear icon --->
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                <div class="rail-button-text" style="display:none">Session</div>
            </button>
            <button class="nav-tab active" data-panel="tasks" data-label="Tasks" onclick="pyview.switchPanel('tasks')" title="Tasks" data-i18n-title="tab_tasks">
                 <!-- AI TODO: better "tasks" icon, not this reused gear icon --->
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                <div class="rail-button-text" style="display:none">Tasks</div>
            </button>
            <button class="nav-tab active" data-panel="subagents" data-label="Sub-agents" onclick="pyview.switchPanel('subagents')" title="Sub-agents" data-i18n-title="tab_subagents">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></svg>
                <div class="rail-button-text" style="display:none">Sub-agents</div>
            </button>
        </div>
        <div class="resize-handle" id="rightpanelResize"></div>

        {{pyview.current_view.render()}}
    '''
    def __init__(self, subject:UiApp, parent: UiAppView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.workspace_view = RightPanelWorkspace(subject, self)
        self.session_view = RightPanelSession(subject, self)
        self.subagents_view = RightPanelSubagents(subject, self)
        self.tasks_view = RightPanelTasks(subject, self)
        
        self.current_view = self.workspace_view

    @property
    def main_panel(self) -> MainView:
        return self.parent.main_panel

    @property
    def current_session(self) -> Session | None:
        tab = self.main_panel.selected_tab_view
        if tab is not None and hasattr(tab, "session"):
            subj = tab.session
            if isinstance(subj, Session):
                return subj
        return None

    def switchPanel(self, name):
        if name == "workspace" and self.current_view != self.workspace_view:
            self.current_view = self.workspace_view
        if name == "session" and self.current_view != self.session_view:
            self.current_view = self.session_view
        if name == "subagents" and self.current_view != self.subagents_view:
            self.current_view = self.subagents_view
        if name == "tasks" and self.current_view != self.tasks_view:
            self.current_view = self.tasks_view
        self.update()