from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.skills.skill import SkillModel
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.skill.rightpanel_skill import RightPanelSkill
    from ui.app import UiApp



class RightPanelSkillInfo(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Info</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            <div class="settings-card" style="margin-bottom:8px">
                <div class="detail-row">
                    <div class="detail-row-label">Description</div>
                    <div class="detail-row-value" style="white-space:pre-line;max-height:120px;overflow:auto;font-size:12px">{{ pyview.description }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Version</div>
                    <div class="detail-row-value">{{ pyview.version_number }}</div>
                </div>
            </div>
        </div>
    '''

    def __init__(self, subject: SkillModel, parent: RightPanelSkill, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def description(self) -> str:
        s = self.subject
        return s.description if s else ""

    @property
    def version_number(self) -> str:
        s = self.subject
        if s and s.latest_skill_version:
            return str(s.latest_skill_version.version_number)
        return "\u2014"

