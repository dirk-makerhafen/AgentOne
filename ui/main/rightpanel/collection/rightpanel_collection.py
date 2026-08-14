"""Right panel tabs for a DataCollection (activity + derived flows)."""
from __future__ import annotations

from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.main.rightpanel.collection.rightpanel_collection_activity import RightPanelCollectionActivity
from ui.main.rightpanel.collection.rightpanel_collection_derived import RightPanelCollectionDerived

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from server.models.collections.data_collection import DataCollection

class RightPanelCollection(ModelView):
    DOM_ELEMENT = "aside"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="sidebar-nav">
            <button class="nav-tab{% if pyview.current_tab_name == "activity" %} active{% endif %}" data-panel="activity" data-label="Activity" onclick="pyview.switchTab('activity')" title="Activity">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
            </button>
            <button class="nav-tab{% if pyview.current_tab_name == "derived" %} active{% endif %}" data-panel="derived" data-label="Derived" onclick="pyview.switchTab('derived')" title="Derived">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
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

    def __init__(self, subject: DataCollection, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.current_tab_name = None
        self.current_tab = None

    def switchTab(self, name: str) -> None:
        if name == self.current_tab_name:
            return 
        if name not in ["activity", "derived"]:
            return
        self.current_tab_name = name
        if self.current_tab:
            self.current_tab.delete(remove_from_dom=False)
        if name == "activity":
            self.current_tab = RightPanelCollectionActivity(self.subject, self)
        elif name == "derived":
            self.current_tab = RightPanelCollectionDerived(self.subject, self)
        self.update()
