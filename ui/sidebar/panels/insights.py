from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.main.insights.dashboard import DashboardView
from ui.main.insights.analytics import AnalyticsView
from ui.main.insights.providers import ProvidersView
from ui.main.insights.models import ModelsView

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
                <button class="panel-head-btn" onclick="pyview.refresh()" title="Refresh" aria-label="Refresh">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="insights-nav">
            {% for item in pyview.nav_items %}
            <div class="insights-nav-item{% if pyview.active_view == item.view %} active{% endif %}" onclick="pyview.openPanel('{{ item.method }}')">
                <span class="insights-nav-icon">{{ item.icon|safe }}</span>
                <span class="insights-nav-text">
                    <span class="insights-nav-title">{{ item.title }}</span>
                    <span class="insights-nav-desc">{{ item.desc }}</span>
                </span>
            </div>
            {% endfor %}
        </div>
    '''

    NAV_ITEMS = (
        {
            "method": "openDashboard", "view": "DashboardView", "title": "Dashboard",
            "desc": "Agent counts, task call statuses and recent activity.",
            "icon": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
        },
        {
            "method": "openAnalytics", "view": "AnalyticsView", "title": "Token Analytics",
            "desc": "Tokens over time, time to first token and throughput.",
            "icon": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
        },
        {
            "method": "openProviders", "view": "ProvidersView", "title": "Providers",
            "desc": "Limits, API keys and usage per provider.",
            "icon": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
        },
        {
            "method": "openModels", "view": "ModelsView", "title": "Models",
            "desc": "Catalog, leaderboard ranks and provider coverage.",
            "icon": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>',
        },
    )

    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self._dashboard_opened = False

    @property
    def nav_items(self):
        return self.NAV_ITEMS

    @property
    def active_view(self) -> str:
        tab = getattr(self.root_view.main_panel, "selected_tab_view", None)
        return type(tab).__name__ if tab is not None else ""

    def panel_activated(self) -> None:
        #if self._dashboard_opened:
        #    return
        self._dashboard_opened = True
        self.openDashboard()

    def openPanel(self, panel):
        if panel == "openDashboard":
            self.openDashboard()
        if panel == "openAnalytics":
            self.openAnalytics()
        if panel == "openModels":
            self.openModels()
        if panel == "openProviders":
            self.openProviders()
            

    def openDashboard(self) -> None:
        self.root_view.main_panel.create_and_open_tab(DashboardView, self.subject)

    def openAnalytics(self) -> None:
        self.root_view.main_panel.create_and_open_tab(AnalyticsView, self.subject)

    def openProviders(self) -> None:
        self.root_view.main_panel.create_and_open_tab(ProvidersView, self.subject)

    def openModels(self) -> None:
        self.root_view.main_panel.create_and_open_tab(ModelsView, self.subject)

    def refresh(self) -> None:
        self.root_view.main_panel.create_and_open_tab(DashboardView, self.subject)
