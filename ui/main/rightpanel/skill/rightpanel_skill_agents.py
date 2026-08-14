from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.skills.skill import SkillModel
from server.models.agents.agent import AgentModel
from ui.lib.model_view import ModelView


if TYPE_CHECKING:
    from ui.main.rightpanel.skill.rightpanel_skill import RightPanelSkill
    from ui.app import UiApp



class RightPanelSkillAgents(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Agents</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% if pyview.agents %}
                {% for agent in pyview.agents %}
                <div style="display:flex;align-items:center;gap:6px;padding:6px 2px;font-size:12px;border-bottom:1px solid var(--border,.05)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                    <span style="font-weight:500">{{ agent.name }}</span>
                </div>
                {% endfor %}
            {% else %}
                <div style="font-size:12px;color:var(--muted);padding:8px">No agents use this skill.</div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: SkillModel, parent: RightPanelSkill, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def agents(self) -> list:
        s = self.subject
        if not s:
            return []
        return list(AgentModel.objects.filter(
            latest_agent_version__agent_settings__skillNames__contains=[s.name],
        ).order_by("name"))
