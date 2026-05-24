"""Sidebar panel for named pipes — list pipes, open detail, create consumers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.models.pipe import NamedPipe
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
from ui.main.pipe.create import PipeCreateView, PipeSubscriptionCreateView
from ui.main.pipe.pipe import PipeDetailView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


class SidebarPanelPipe(ModelView):
    DOM_ELEMENT_CLASS = "cron-item"
    TEMPLATE_STR = '''
        <div class="cron-header" onclick="pyview.open_pipe_details()">
            <span class="cron-name" title="{{ pyview.subject.name }}">{{ pyview.subject.name }}</span>
            <span class="cron-profile-badge">{{ pyview.sub_count }} consumers</span>
        </div>
    '''

    def __init__(self, subject: NamedPipe, parent: QuerySetView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.parent.root_view

    @property
    def sub_count(self) -> int:
        return self.subject.subscriptions.count()

    def open_pipe_details(self):
        self.root_view.main_panel.create_and_open_tab(PipeDetailView, self.subject)


class SidebarPanelPipes(ModelView):
    DOM_ELEMENT_CLASS = "panel-view active"
    TEMPLATE_STR = '''
        <div class="panel-head">
            <span>Named pipes</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" onclick="pyview.refreshList()" title="Refresh">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
                <button class="panel-head-btn" onclick="pyview.openCreatePipe()" title="New pipe">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </button>
            </div>
        </div>
        {{ pyview.pipe_list.render() }}
    '''

    def __init__(self, subject: UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self.pipe_list = QuerySetView(
            subject=subject.pipes.root(),
            parent=self,
            item_class=SidebarPanelPipe,
            dom_element_class="cron-list",
        )

    def openCreatePipe(self):
        self.root_view.main_panel.create_and_open_tab(
            PipeCreateView, self.subject
        )

    def refreshList(self):
        self.pipe_list.update()
