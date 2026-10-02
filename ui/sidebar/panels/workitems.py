"""Work Items sidebar panel — a compact, filterable list of durable work.

Follows the same shape as the other sidebar panels: a ``QuerySetView`` of
per-row views, a ``panel_activated`` hook that opens the board, and a
``set_project_filter`` hook so the global project selector scopes the list.

``MainView._update_sidebar_active`` refreshes a fixed list of attribute names
on the selected panel, so ``workitem_list`` must exist for the panel to be
picked up by that loop.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView
from ui.main.workitems.board_data import (
    STATUS_COLUMNS,
    scoped_queryset,
)

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.app_view import UiAppView
    from ui.sidebar.sidebar import SidebarView


_STATUS_LABELS = dict(STATUS_COLUMNS)


class SidebarPanelWorkItem(ModelView):
    """One row in the sidebar list — a status line above the title."""

    TEMPLATE_STR = '''
        <div class="kanban-list-status">{{ pyview.status_label }}<span style="opacity:.5"> · #{{ pyview.item_id }}</span></div>
        <div class="kanban-list-title">{{ pyview.title }}</div>
    '''

    def __init__(self, subject, parent: QuerySetView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.parent.root_view

    @property
    def item_id(self):
        return getattr(self.subject, "pk", None)

    @property
    def title(self) -> str:
        return getattr(self.subject, "title", "") or f"Work item {self.item_id}"

    @property
    def status_label(self) -> str:
        return _STATUS_LABELS.get(getattr(self.subject, "status", ""), "?")

    @property
    def DOM_ELEMENT_CLASS(self) -> str:
        cls = "kanban-list-item"
        if self._is_current_item():
            cls += " selected"
        return cls

    def _is_current_item(self) -> bool:
        main_panel = getattr(self.root_view, "main_panel", None)
        tab = getattr(main_panel, "selected_tab_view", None)
        return tab is not None and getattr(tab, "selected_id", None) == self.item_id


class SidebarPanelWorkItems(ModelView):
    DOM_ELEMENT_CLASS = "panel-view kanban-pane"
    TEMPLATE_STR = '''
        <div class="panel-head">
            <span>Work Items</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" onclick="pyview.open_board()" title="Open board" aria-label="Open board">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M8 4v16"/><path d="M16 4v16"/><path d="M3 10h18"/></svg>
                </button>
                <button class="panel-head-btn" onclick="pyview.reload()" title="Refresh" aria-label="Refresh">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                </button>
            </div>
        </div>
        <div class="kanban-filter-stack">
            <select onchange="pyview.set_status_filter(this.value)">
                <option value="">All statuses</option>
                {% for value, label in pyview.statuses %}
                <option value="{{ value }}" {% if value == pyview.status_filter %}selected{% endif %}>{{ label }}</option>
                {% endfor %}
            </select>
            <div class="kanban-new-task-row">
                <input placeholder="Search titles..." oninput="pyview.set_search(this.value)">
            </div>
        </div>
        <div class="kanban-summary">{{ pyview.count }} item(s) &middot; {{ pyview.active_count }} needing a human</div>
        <div class="kanban-list">
            {{ pyview.workitem_list.render() }}
        </div>
    '''

    def __init__(self, subject: "UiApp", parent: "SidebarView", **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self.project_id: int | None = getattr(parent, "selected_project_id", None)
        self.status_filter = ""
        self.search = ""
        self.workitem_list = QuerySetView(
            subject=scoped_queryset(self.project_id),
            parent=self,
            item_class=SidebarPanelWorkItem,
        )

    @property
    def statuses(self) -> tuple[tuple[str, str], ...]:
        return STATUS_COLUMNS

    @property
    def _scoped(self):
        query = scoped_queryset(self.project_id)
        if self.status_filter:
            query = query.filter(status=self.status_filter)
        if self.search:
            query = query.filter(title__icontains=self.search)
        return query

    @property
    def count(self) -> int:
        return self._scoped.count()

    @property
    def active_count(self) -> int:
        return self._scoped.filter(status__in=["in_review", "blocked"]).count()

    def _refresh_list(self) -> None:
        # Filtering happens in SQL via _scoped, not in a QuerySetView
        # filter_function: the same predicate in both places ran a second
        # Python pass over every row on every render, and the two could
        # silently disagree about what "filtered" means.
        self.workitem_list.query = self._scoped
        self.workitem_list._recreate()

    def set_status_filter(self, value: str) -> None:
        self.status_filter = (value or "").strip()
        self._refresh_list()
        self.update()

    def set_search(self, value: str) -> None:
        self.search = (value or "").strip()
        self._refresh_list()
        self.update()

    def set_project_filter(self, project_id: int | None) -> None:
        self.project_id = project_id
        self._refresh_list()
        self.update()

    def reload(self) -> None:
        self._refresh_list()
        self.update()

    def open_board(self) -> None:
        from ui.main.workitems.board import WorkItemsBoard

        self.root_view.main_panel.create_and_open_tab(WorkItemsBoard, self.subject)

    def panel_activated(self) -> None:
        """Clicking the Work Items rail icon opens the board."""
        try:
            self.open_board()
        except Exception:
            pass
