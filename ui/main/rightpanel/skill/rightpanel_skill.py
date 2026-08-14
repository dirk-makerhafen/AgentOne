from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.skills.skill import SkillModel
from ui.lib.model_view import ModelView
from ui.main.rightpanel.skill.rightpanel_skill_agents import RightPanelSkillAgents
from ui.main.rightpanel.skill.rightpanel_skill_info import RightPanelSkillInfo

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp



class RightPanelSkill(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="sidebar-nav">
            <button class="nav-tab{% if pyview.current_tab_name == "info" %} active{% endif %}" data-panel="info" data-label="Info" onclick="pyview.switchTab('info')" title="Info">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "agents" %} active{% endif %}" data-panel="agents" data-label="Agents" onclick="pyview.switchTab('agents')" title="Agents">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
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

    def __init__(self, subject: SkillModel, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.current_tab_name = None
        self.current_tab = None

    def switchTab(self, name: str) -> None:
        if name == self.current_tab_name:
            return 
        if name not in ["info", "agents"]:
            return
        self.current_tab_name = name
        if self.current_tab:
            self.current_tab.delete(remove_from_dom=False)
        if name == "info":
            self.current_tab = RightPanelSkillInfo(self.subject, self)
        elif name == "agents":
            self.current_tab = RightPanelSkillAgents(self.subject, self)
        self.update()
