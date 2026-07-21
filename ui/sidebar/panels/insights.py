from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.main.insights.dashboard import DashboardView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView

class SidebarPanelInsights(ModelView):
    DOM_ELEMENT_CLASS = "panel-view"
    TEMPLATE_STR = '''
        <!-- Insights panel -->
        <div class="panel-head">
            <span data-i18n="tab_insights">Insights</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" onclick="pyview.openDashboard()" title="Open dashboard" aria-label="Open dashboard">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                </button>
                <button class="panel-head-btn" onclick="pyview.refresh()" title="Refresh" aria-label="Refresh">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="panel-head-sub" style="padding:8px 12px">
            <div style="font-size:12px;color:var(--muted);line-height:1.5">
                Overview of your agent framework — agent counts, task call statuses,
                and recent activity across all agents and sessions.
            </div>
        </div>
    '''

    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self._dashboard_opened = False

    def panel_activated(self) -> None:
        #if self._dashboard_opened:
        #    return
        self._dashboard_opened = True
        self.openDashboard()

    def openDashboard(self) -> None:
        self.root_view.main_panel.create_and_open_tab(DashboardView, self.subject)

    def refresh(self) -> None:
        self.root_view.main_panel.create_and_open_tab(DashboardView, self.subject)
