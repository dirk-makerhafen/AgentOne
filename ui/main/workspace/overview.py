"""Workspaces overview: card/list grid of all workspaces.

Opened from the sidebar workspaces panel (grid icon).  Clicking a card
opens the single-workspace detail tab.  Search and the card/list toggle
are client-side (no server roundtrip); creation reuses CreateWorkspace.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView
from ui.main.workspace.create import CreateWorkspace
from ui.main.workspace.workspace import (
    WS_FILTER_SCRIPT,
    Workspace,
    current_session_workspace_pk,
    workspace_card_data,
)

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


class WorkspacesOverview(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="ws-ov-topbar">
            <div class="ws-ov-breadcrumb">
                <span class="ws-ov-crumb">Workspaces</span>
            </div>
            <div class="ws-ov-search">
                <svg class="ws-ov-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                <input id="wsOvSearch" placeholder="Search workspaces..." oninput="wsOvFilter()" autocomplete="off">
            </div>
            <button class="ws-ov-primary" onclick="pyview.openCreate()">＋ New workspace</button>
        </div>
        <div class="main-view-body">
            <div class="main-view-content ws-ov-content">
                <div class="ws-ov-heading-row">
                    <div>
                        <h1 class="ws-ov-title">Workspaces</h1>
                        <div class="ws-ov-subtitle">{{ pyview.workspaces|length }} workspace(s)</div>
                    </div>
                    <div class="ws-ov-view-controls">
                        <button class="ws-ov-view-btn{% if pyview.view_mode == "grid" %} active{% endif %}" onclick="pyview.setView('grid')" title="Card view">▦</button>
                        <button class="ws-ov-view-btn{% if pyview.view_mode == "list" %} active{% endif %}" onclick="pyview.setView('list')" title="List view">☷</button>
                    </div>
                </div>
                <div class="ws-ov-grid{% if pyview.view_mode == "list" %} ws-ov-list{% endif %}" id="wsOvGrid">
                    {% for ws in pyview.workspaces %}
                    <div class="ws-ov-card" data-name="{{ ws.name|lower }} {{ ws.path|lower }}" onclick="pyview.openWorkspace({{ ws.pk }})">
                        <div class="ws-ov-card-top">
                            <div class="ws-ov-icon"{% if ws.color %} style="background:{{ ws.color }}"{% endif %}>
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                            </div>
                             <h3>{{ ws.name }}</h3>
                        </div>
                        <div class="ws-ov-card-info">
                           
                            <div class="ws-ov-path" title="{{ ws.path }}">{{ ws.path }}</div>
                            <div class="ws-ov-desc">{{ ws.description if ws.description else "No description yet." }}</div>
                        </div>
                        <div class="ws-ov-card-bottom">
                            <div class="ws-ov-status">
                                {% if ws.pk == pyview.active_workspace_pk %}
                                <span class="ws-ov-dot"></span> Active
                                {% else %}
                                <span class="ws-ov-dot ws-ov-dot--idle"></span> Idle
                                {% endif %}
                            </div>
                            <span>{{ ws.session_count }} session(s) · {{ ws.agent_count }} agent(s)</span>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                <div class="ws-ov-empty" id="wsOvEmpty" style="display:none">
                    <div class="ws-ov-empty-icon">⌕</div>
                    <h2>No workspaces found</h2>
                    <div>Try another search or create a new workspace.</div>
                </div>
            </div>
        </div>
    ''' + WS_FILTER_SCRIPT

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._view_mode = "grid"

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    @property
    def view_mode(self) -> str:
        return self._view_mode

    @property
    def workspaces(self) -> list[dict]:
        from server.models.workspace import WorkspaceModel

        try:
            all_ws = list(WorkspaceModel.objects.all().order_by("name"))
        except Exception:
            return []
        return [workspace_card_data(ws) for ws in all_ws]

    @property
    def active_workspace_pk(self) -> int | None:
        try:
            return current_session_workspace_pk(self._find_main_view())
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def setView(self, mode: str) -> None:
        if mode in ("grid", "list"):
            self._view_mode = mode
            self.update()

    def openWorkspace(self, pk: int) -> None:
        from server.models.workspace import WorkspaceModel

        try:
            ws = WorkspaceModel.objects.get(pk=int(pk))
        except (WorkspaceModel.DoesNotExist, ValueError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(Workspace, ws)

    def openCreate(self) -> None:
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(CreateWorkspace, self.subject)

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent
