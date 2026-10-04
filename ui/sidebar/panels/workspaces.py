"""Sidebar panel for workspaces, rendered as a path-derived tree.

Workspaces have no explicit parent field: a workspace whose path lives
inside another workspace's path (``/a/b`` inside ``/a``) renders as a
subworkspace of it.  Pure tree-building lives in
:func:`build_workspace_tree` so it stays unit-testable without a DB.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from server.models.workspace import WorkspaceModel
from ui.lib.model_view import ModelView
from ui.main.workspace.create import CreateWorkspace
from ui.main.workspace.overview import WorkspacesOverview
from ui.main.workspace.workspace import (
    Workspace,
    current_session_workspace_pk,
    norm_workspace_path,
    workspace_parent_map,
)

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


def _norm(path: str) -> str:
    """Normalize a workspace path for prefix comparison."""
    return norm_workspace_path(path)


def build_workspace_tree(items: list) -> list[dict]:
    """Build DFS-ordered tree rows from workspace-like objects.

    Each item needs ``pk``, ``name`` and ``path`` attributes (``color`` is
    optional and defaults to "").  Returns a flat list of row dicts
    (``pk``, ``name``, ``path``, ``display_path``, ``color``, ``depth``,
    ``has_children``) in pre-order: parents before children, siblings
    sorted by name (roots) or by name within a parent.
    """
    by_pk = {}
    for ws in items:
        by_pk[ws.pk] = ws

    # Parent = longest proper path-prefix among the other workspaces.
    parent_of = workspace_parent_map(items)
    normed = {ws.pk: _norm(ws.path) for ws in items}

    children: dict[int | None, list] = {}
    for ws in items:
        children.setdefault(parent_of[ws.pk], []).append(ws)
    for siblings in children.values():
        siblings.sort(key=lambda w: (w.name or "").lower())

    rows: list[dict] = []

    def _walk(pk: int | None, depth: int, parent_path: str | None) -> None:
        for ws in children.get(pk, []):
            mine = normed[ws.pk]
            if parent_path and mine.startswith(parent_path + os.sep):
                display_path = os.path.relpath(mine, parent_path)
            else:
                display_path = ws.path
            rows.append(
                {
                    "pk": ws.pk,
                    "name": ws.name or mine,
                    "path": ws.path,
                    "display_path": display_path,
                    "color": getattr(ws, "color", "") or "",
                    "depth": depth,
                    "has_children": bool(children.get(ws.pk)),
                }
            )
            _walk(ws.pk, depth + 1, mine)

    _walk(None, 0, None)
    return rows


class SidebarPanelWorkspaces(ModelView):
    DOM_ELEMENT_CLASS = "panel-view"
    TEMPLATE_STR = '''
        <!-- Workspaces panel -->
        <div class="panel-head">
            <span data-i18n="tab_workspaces">Workspaces</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" onclick="pyview.openOverview()" title="All workspaces" aria-label="All workspaces">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
                </button>
                <button class="panel-head-btn" onclick="pyview.openWorkspaceCreate()" title="Add space" data-i18n-title="workspace_add_title" aria-label="Add space">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </button>
            </div>
        </div>
        <div class="panel-head-sub" data-i18n="workspace_desc"></div>
        <div class="ws-tree" id="workspacesPanel">
            {% for row in pyview.tree_rows %}
            <div class="ws-row{% if row.pk == pyview.current_workspace_pk %} active{% endif %}" style="padding-left:{{ 8 + row.depth * 18 }}px" onclick="pyview.open_workspace({{ row.pk }})" title="{{ row.path }}">
                {% if row.has_children and row.pk in pyview.collapsed %}
                <span class="ws-tree-folder ws-tree-folder--toggle" title="Expand" onclick="event.stopPropagation();pyview.toggle_collapse({{ row.pk }})">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3h5l4 4v3H6V5a2 2 0 0 1 2-2z"/><path d="M2 11v8a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-8z"/><path d="M2 11h20"/></svg>
                </span>
                {% elif row.has_children %}
                <span class="ws-tree-folder ws-tree-folder--toggle" title="Collapse" onclick="event.stopPropagation();pyview.toggle_collapse({{ row.pk }})">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2v5H3z"/><path d="M3 12h18v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
                </span>
                {% else %}
                <span class="ws-tree-folder" style="color:{{ row.color }}">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                </span>
                {% endif %}
                <div class="ws-row-info">
                    <div class="ws-row-name">
                        {{ row.name }}
                        {% if row.pk == pyview.active_workspace_pk %}
                        <span class="detail-badge active" style="margin-left:6px;font-size:9px;padding:1px 6px">ACTIVE</span>
                        {% endif %}
                    </div>
                    <div class="ws-row-path">{{ row.display_path }}</div>
                </div>
            </div>
            {% endfor %}
        </div>
    '''

    def __init__(self, subject: UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view
        self._collapsed: set[int] = set()
        # Parents the user explicitly toggled — everything else with
        # children starts collapsed (see tree_rows).
        self._touched: set[int] = set()
        # MainView._update_sidebar_active looks for a ``workspace_list``
        # attribute and calls update() on it — the panel itself fills that role.
        self.workspace_list = self
        try:
            # Redis observable path: "WorkspaceModel" is the `any` key every
            # WorkspaceModel write notifies on (create/update/delete alike).
            # Published by the workspace UI views, the API ViewSet and the
            # wiki/projectmanager scripts.
            from ui.lib.model_view import orm_subscribe

            orm_subscribe(self, "WorkspaceModel", self._on_orm_event)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    @property
    def collapsed(self) -> set[int]:
        return self._collapsed

    @property
    def tree_rows(self) -> list[dict]:
        workspaces = list(WorkspaceModel.objects.all())
        rows = build_workspace_tree(workspaces)
        # Subtrees start collapsed; only user-expanded parents stay open.
        for row in rows:
            if row["has_children"] and row["pk"] not in self._touched:
                self._collapsed.add(row["pk"])
        # Hide descendants of collapsed nodes (the collapsed node itself stays).
        visible: list[dict] = []
        # Depths at which an ancestor is collapsed hide everything below them.
        collapsed_at_depth: dict[int, bool] = {}
        for row in rows:
            depth = row["depth"]
            # Drop stale deeper levels when dedenting.
            for d in [k for k in collapsed_at_depth if k >= depth]:
                del collapsed_at_depth[d]
            if any(collapsed_at_depth.get(d, False) for d in range(depth)):
                continue
            visible.append(row)
            if row["has_children"] and row["pk"] in self._collapsed:
                collapsed_at_depth[depth] = True
        return visible

    @property
    def current_workspace_pk(self) -> int | None:
        """Workspace of the currently open detail tab (row highlight)."""
        tab = self.root_view.main_panel.selected_tab_view
        if tab is not None and isinstance(tab, Workspace):
            try:
                return tab.subject.pk
            except Exception:
                return None
        return None

    @property
    def active_workspace_pk(self) -> int | None:
        """Workspace bound to the current chat session (ACTIVE badge)."""
        try:
            return current_session_workspace_pk(self.root_view.main_panel)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_orm_event(self, key=None, model=None, pk=None, action=None, data=None) -> None:
        """Redis observable callback: any WorkspaceModel write re-renders."""
        self.update()

    def toggle_collapse(self, pk: int) -> None:
        pk = int(pk)
        self._touched.add(pk)
        if pk in self._collapsed:
            self._collapsed.discard(pk)
        else:
            self._collapsed.add(pk)
        self.update()

    def open_workspace(self, pk: int) -> None:
        try:
            ws = WorkspaceModel.objects.get(pk=int(pk))
        except (WorkspaceModel.DoesNotExist, ValueError):
            return
        self.root_view.main_panel.create_and_open_tab(Workspace, ws)

    def openOverview(self):
        self.root_view.main_panel.create_and_open_tab(WorkspacesOverview, self.subject)

    def openWorkspaceCreate(self):
        self.root_view.main_panel.create_and_open_tab(CreateWorkspace, self.subject)
