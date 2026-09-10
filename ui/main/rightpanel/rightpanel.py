from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.main.rightpanel.cron.rightpanel_cron import RightPanelCron
from ui.main.rightpanel.session.rightpanel_session import RightPanelSession
from ui.main.rightpanel.workspace.rightpanel_workspace import RightPanelWorkspace
from ui.main.rightpanel.collection.rightpanel_collection import RightPanelCollection
from ui.main.rightpanel.agent.rightpanel_agent import RightPanelAgent
from ui.main.rightpanel.project.rightpanel_project import RightPanelProject
from ui.main.rightpanel.skill.rightpanel_skill import RightPanelSkill
from ui.main.rightpanel.provider.rightpanel_provider import RightPanelProvider
from ui.main.rightpanel.model.rightpanel_model import RightPanelModel

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.app_view import UiAppView


class RightPanel(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        {% if pyview.current_view %}
            {{ pyview.current_view.render() }}
        {% else %}
            <div style="flex:1;padding:8px">
                <div style="font-size:12px;color:var(--muted);text-align:center;margin-top:40%">None Selected</div>
            </div>
        {% endif %}
    '''

    def __init__(self, subject: UiApp, parent: UiAppView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.current_view: ModelView | None = None
       
    def close(self):
        self._tabs = []
        self._tab_map = {}
        self.current_view = None
        self.update()

    def set_view(self, view_class, subject):
        if self.current_view:
            self.current_view.delete(remove_from_dom=False)
        self.current_view = view_class(subject, self)
        self.update()
      