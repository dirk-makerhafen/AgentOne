from __future__ import annotations
from typing import TYPE_CHECKING
from ui.main.agent.agent_view import AgentView
from ui.main.insights.insights import MainInsightsView
from ui.main.logs.logs import MainLogsView
from ui.main.project.project_view import ProjectView
from ui.main.settings.settings import SettingsView

from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp

class MainView(ModelView):
    DOM_ELEMENT = "main"
    DOM_ELEMENT_CLASS = "main"
    TEMPLATE_STR = """
        {% if pyview.selected_tab_view %}
            {{ pyview.selected_tab_view.render() }}
        {% else %}
            Open something
        {% endif %}
    """
   
    
    def __init__(self, subject: "UiApp", parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.open_tabs = {}
        self.selected_tab_id = ""
        self.selected_tab_view = None

    def create_and_open_tab(self, view_class, subject):
        uid = getattr(subject, "id", getattr(subject, "uid", id(subject)))
        key = f"{view_class.__name__}__{uid}"
        existing_tab = self.open_tabs.get(key, None)
        if existing_tab is not None:
            self.select_tab(key)
            return existing_tab
        self.open_tabs[key] = view_class(subject=subject, parent=self)
        self.select_tab(key)
        
        return self.open_tabs[key]

    def select_tab(self, tab_id):
        if tab_id not in self.open_tabs:
            print(f"No tab with id{tab_id}")
            return 
        self.selected_tab_id = tab_id
        self.selected_tab_view = self.open_tabs[tab_id]
        self.update()
