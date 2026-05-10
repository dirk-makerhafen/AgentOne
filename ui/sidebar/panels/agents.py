from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.agents.agent import AgentModel
from ui.app import UiApp
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.lib.queryset_view import QuerySetView
from ui.main.agent.agent_view import AgentView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView

class SidebarPanelAgent(ModelView):
    DOM_ELEMENT_CLASS = "profile-card"    
    TEMPLATE_STR = '''
        <div class="profile-card-header" onclick="pyview.open_agent_details()">
            <div style="min-width:0;flex:1">
                <div class="profile-card-name is-active">
                    <span class="profile-opt-badge stopped" title="Gateway stopped"></span>
                        default 
                    <span style="opacity:.5">(default)</span>
                    <span style="color:var(--link);font-size:10px;font-weight:600;margin-left:6px">
                        ACTIVE
                    </span>
                </div>
                <div class="profile-card-meta">gemma4:e4b · ollama-launch · 89 skills</div>
            </div>
        </div>
    '''
    def __init__(self, subject: AgentModel, parent: QuerySetView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.parent.root_view
    
    def open_agent_details(self):
        self.root_view.main_panel.create_and_open_tab(AgentView, self.subject)
      

class SidebarPanelAgents(ModelView):
    DOM_ELEMENT_CLASS = "panel-view"    
    TEMPLATE_STR = '''
        <!-- Agents panel -->
        <div class="panel-head">
            <span data-i18n="tab_profiles">Agent profiles</span>
            <div class="panel-head-actions">
            <button class="panel-head-btn" onclick="openProfileCreate()" title="New profile" data-i18n-title="new_profile" aria-label="New profile"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button>
            </div>
        </div>
        <div style="flex:1;overflow-y:auto;padding:8px" id="profilesPanel">
            {{ pyview.agent_list.render() }}
        </div>
    '''    
    
    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.uid = "panelProfiles"
        self.root_view: UiAppView = parent.root_view

        self.agent_list = QuerySetView(
            subject=subject.agents.root(),
            parent=self,
            item_class=SidebarPanelAgent,
        )
