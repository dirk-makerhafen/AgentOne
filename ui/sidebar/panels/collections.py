"""Sidebar panel for Data Collections (streams + ordered sets)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.models.collections import DataCollection
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
from ui.main.collections.create import CollectionCreateView
from ui.main.collections.collection_detail import CollectionDetailView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


class SidebarPanelCollectionItem(ModelView):
    DOM_ELEMENT_CLASS = "cron-item"
    TEMPLATE_STR = '''
        <div class="cron-header" onclick="pyview.open_details()">
            <span class="cron-name" title="{{ pyview.subject.name }}">
                {{ pyview.subject.name }}
            </span>
            <span class="cron-profile-badge">
                {{ pyview.subject.get_collection_type_display() }}
                &middot; {{ pyview.item_count }} items
            </span>
        </div>
    '''

    def __init__(self, subject: DataCollection, parent: QuerySetView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.parent.root_view

    @property
    def item_count(self) -> int:
        return self.subject.items.count()

    def open_details(self):
        self.root_view.main_panel.create_and_open_tab(CollectionDetailView, self.subject)


class SidebarPanelCollections(ModelView):
    DOM_ELEMENT_CLASS = "panel-view active"
    TEMPLATE_STR = '''
        <div class="panel-head">
            <span>Data flows</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" onclick="pyview.refreshList()" title="Refresh">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
                <button class="panel-head-btn" onclick="pyview.openCreate()" title="New data flow">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </button>
            </div>
        </div>
        {{ pyview.collection_list.render() }}
    '''

    def __init__(self, subject: UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        qs = DataCollection.objects.all().order_by("name")
        self.collection_list = QuerySetView(
            subject=qs,
            parent=self,
            item_class=SidebarPanelCollectionItem,
            dom_element_class="cron-list",
        )

    def openCreate(self):
        self.root_view.main_panel.create_and_open_tab(
            CollectionCreateView, self.subject
        )

    def refreshList(self):
        self.collection_list.update()
