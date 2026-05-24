from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.cron import Cronjob
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
from ui.main.cron.create import CronCreateView
from ui.main.cron.cron import CronView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


class SidebarPanelCronjob(ModelView):
    DOM_ELEMENT_CLASS = "cron-item"
    TEMPLATE_STR = '''
        <div class="cron-header" onclick="pyview.open_cron_details()">
            <span class="cron-name" title="{{ pyview.subject.name }}">{{ pyview.subject.name }}</span>
            <span class="cron-profile-badge">{{ pyview.subject.agent.name }}</span>
            <span class="cron-status {% if pyview.subject.is_active %}active{% endif %}">
                {% if pyview.subject.is_active %}active{% else %}paused{% endif %}
            </span>
        </div>
    '''
    def __init__(self, subject: Cronjob, parent: QuerySetView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.parent.root_view

    def open_cron_details(self):
        self.root_view.main_panel.create_and_open_tab(CronView, self.subject)


class SidebarPanelCronjobs(ModelView):
    DOM_ELEMENT_CLASS = "panel-view active"
    TEMPLATE_STR = '''
        <div class="panel-head">
            <span data-i18n="scheduled_jobs">Scheduled jobs</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" onclick="pyview.refreshList()" title="Refresh job list">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
                <button class="panel-head-btn" onclick="pyview.openCronCreate()" title="New job" data-i18n-title="new_job">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </button>
            </div>
        </div>
        {{ pyview.cronjob_list.render() }}
    '''

    def __init__(self, subject: UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self.cronjob_list = QuerySetView(
            subject=subject.cronjobs.root(),
            parent=self,
            item_class=SidebarPanelCronjob,
            dom_element_class="cron-list",
        )

    def openCronCreate(self):
        self.root_view.main_panel.create_and_open_tab(CronCreateView, self.subject)

    def refreshList(self):
        self.cronjob_list.update()
