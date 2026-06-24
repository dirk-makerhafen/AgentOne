from __future__ import annotations
from typing import TYPE_CHECKING

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

    def close_tab(self, view) -> None:
        key = None
        for k, v in self.open_tabs.items():
            if v is view:
                key = k
                break
        if key:
            del self.open_tabs[key]
        if self.selected_tab_view is view:
            self.selected_tab_view = None
            self.selected_tab_id = ""
            if self.open_tabs:
                last_key = list(self.open_tabs.keys())[-1]
                self.select_tab(last_key)
            else:
                self.parent.rightpanel._update_context()
                self.update()
                self._titlebar_update()
                self._update_sidebar_active()

    def select_tab(self, tab_id):
        if tab_id not in self.open_tabs:
            print(f"No tab with id{tab_id}")
            return
        self.selected_tab_id = tab_id
        self.selected_tab_view = self.open_tabs[tab_id]
        self.parent.rightpanel._update_context()
        self.update()
        self._titlebar_update()
        self._update_sidebar_active()

    def _titlebar_update(self):
        titlebar = getattr(self.parent, 'titlebar', None)
        if titlebar is not None:
            titlebar.update()

    def _update_sidebar_active(self):
        sidebar = getattr(self.parent, 'sidebar', None)
        if sidebar is None:
            return
        panel = getattr(sidebar, 'selected_panel', None)
        if panel is None:
            return
        for attr in ('agent_list', 'cronjob_list', 'collection_list', 'project_list', 'workspace_list', 'skill_list'):
            lst = getattr(panel, attr, None)
            if lst is not None:
                lst.update()
                break
