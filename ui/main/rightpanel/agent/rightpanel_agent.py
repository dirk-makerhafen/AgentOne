from __future__ import annotations
from typing import TYPE_CHECKING
from django.utils import timezone
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.rightpanel.agent.rightpanel_agent_capabilities import RightPanelAgentCapabilities
from ui.main.rightpanel.agent.rightpanel_agent_info import RightPanelAgentInfo
from ui.main.rightpanel.agent.rightpanel_agent_sessions import RightPanelAgentSessions

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


class RightPanelAgent(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="sidebar-nav">
            <button class="nav-tab{% if pyview.current_tab_name == "info" %} active{% endif %}" data-panel="info" data-label="Info" onclick="pyview.switchTab('info')" title="Info">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "sessions" %} active{% endif %}" data-panel="sessions" data-label="Sessions" onclick="pyview.switchTab('sessions')" title="Sessions">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "capabilities" %} active{% endif %}" data-panel="capabilities" data-label="Capabilities" onclick="pyview.switchTab('capabilities')" title="Capabilities">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
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

    def __init__(self, subject: AgentModel, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.current_tab_name = None
        self.current_tab = None

    def switchTab(self, name: str) -> None:
        if name == self.current_tab_name:
            return 
        if name not in ["info", "sessions", "capabilities"]:
            return
        self.current_tab_name = name
        if self.current_tab:
            self.current_tab.delete(remove_from_dom=False)
        if name == "info":
            self.current_tab = RightPanelAgentInfo(self.subject, self)
        elif name == "sessions":
            self.current_tab = RightPanelAgentSessions(self.subject, self)
        elif name == "capabilities":
            self.current_tab = RightPanelAgentCapabilities(self.subject, self)
        self.update()
