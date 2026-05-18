from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView

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
                <button class="panel-head-btn" id="insightsRefreshBtn" onclick="loadInsights(true)" title="Refresh" aria-label="Refresh">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="panel-head-sub" style="padding:0 12px 8px">
            <select id="insightsPeriod" onchange="loadInsights()" style="width:100%;background:var(--input-bg);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:12px">
                <option value="7">7 days</option>
                <option value="30" selected>30 days</option>
                <option value="90">90 days</option>
                <option value="365">365 days</option>
            </select>
        </div>
    '''

    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
