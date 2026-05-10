from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


class SidebarPanelCron(ModelView):
    DOM_ELEMENT_CLASS = "panel-view active"
    TEMPLATE_STR = '''       
        <!-- Tasks (cron) panel -->
        <div class="panel-head">
            <span data-i18n="scheduled_jobs">Scheduled jobs</span>
            <div class="panel-head-actions">
            <button class="panel-head-btn" id="cronRefreshBtn" onclick="loadCrons(true)" title="Refresh job list" aria-label="Refresh job list"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></button>
            <button class="panel-head-btn" onclick="openCronCreate()" title="New job" data-i18n-title="new_job" aria-label="New job"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button>
            </div>
        </div>
        <div class="cron-list" id="cronList"><div style="padding:12px;color:var(--muted);font-size:12px" data-i18n="loading">Loading...</div></div>
    '''

    def __init__(self, subject:UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.uid = "panelTasks"        
        self.root_view: UiAppView = parent.root_view
