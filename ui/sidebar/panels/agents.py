from __future__ import annotations
from typing import TYPE_CHECKING
from runtime.agents.agent import Agent
from server.models.agents.agent import AgentModel
from server.models.providers.ai_model import AiModel
from ui.app import UiApp
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
from ui.main.agent.agent_view import AgentView
from ui.main.agent.create import AgentCreateView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView

class SidebarPanelAgent(ModelView):
    TEMPLATE_STR = '''
        <div class="profile-card-header" onclick="pyview.open_agent_details()">
            <div style="min-width:0;flex:1">
                <div class="profile-card-name is-active">
                    
                    <span class="profile-opt-badge stopped" title="Gateway stopped"></span>
                    
                    {{ pyview.subject.name }} 
                    
                    <span style="opacity:.5">
                        (default1)
                    </span>
                    
                    <span style="color:var(--link);font-size:10px;font-weight:600;margin-left:6px">
                        ACTIVE
                    </span>
                </div>
                <div class="profile-card-meta">
                    {% if pyview.agent.aimodel %}{{ pyview.agent.aimodel.name }}{% else %}No Model{% endif %} · 
                    {{ pyview.agent.allowedSkills | length }} Skills,
                    {{ pyview.agent.allowedTools | length }} Tools, 
                    {{ pyview.agent.allowedTasks | length }} Tasks, 
                    {{ pyview.agent.allowedCommands | length }} Cmd,  
                </div>
            </div>
        </div>
    '''
    def __init__(self, subject: AgentModel, parent: QuerySetView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.parent.root_view
        self.agent = Agent(subject)

    @property
    def DOM_ELEMENT_CLASS(self):
        cls = "profile-card"
        if self._is_current_item():
            cls += " active"
        return cls

    def _is_current_item(self):
        tab = self.root_view.main_panel.selected_tab_view
        if tab is not None and hasattr(tab, "subject"):
            subj = tab.subject
            if hasattr(subj, "pk"):
                return subj.pk == self.subject.pk
        return False

    def open_agent_details(self):
        self.root_view.main_panel.create_and_open_tab(AgentView, self.subject)
      

class SidebarPanelAgents(ModelView):
    DOM_ELEMENT_CLASS = "panel-view"    
    TEMPLATE_STR = '''
        <!-- Agents panel -->
        <div class="panel-head">
            <span data-i18n="tab_profiles">Agent profiles</span>
            <div class="panel-head-actions">
            <button class="panel-head-btn" onclick="pyview.reloadFromDisk()" title="refresh from disk" data-i18n-title="agents_refresh_title" aria-label="Refresh from disk">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
            </button>
            <button class="panel-head-btn" onclick="pyview.openProfileCreate()" title="New profile" data-i18n-title="new_profile" aria-label="New profile">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </button>
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
            subject = subject.agents.root(),
            parent = self,
            item_class = SidebarPanelAgent,
        )
    def set_project_filter(self, project_id: int | None) -> None:
        if project_id is None:
            self.agent_list.query = self.subject.agents.root()
        else:
            self.agent_list.query = AgentModel.objects.filter(parent_project=project_id)
        self.agent_list._recreate()
        self.update()

    def openProfileCreate(self):
        self.root_view.main_panel.create_and_open_tab(AgentCreateView, self.subject)

    def panel_activated(self) -> None:
        """Show the agents dashboard when the agents sidebar icon is clicked."""
        try:
            from ui.main.agent.overview import AgentsOverview

            self.root_view.main_panel.create_and_open_tab(AgentsOverview, self.subject)
        except Exception:
            pass

    def reloadFromDisk(self):
        pass