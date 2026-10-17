from __future__ import annotations
from typing import TYPE_CHECKING
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.sidebar.sidebar import SidebarView
    from ui.app import UiApp
    from ui.app_view import UiAppView


class SidebarPanelDashboard(ModelView):
    """Sidebar panel behind the dashboard rail button.

    A compact global overview with counts and shortcuts; the full
    latest-chats/projects/work-items view lives in the main panel
    (:class:`GlobalDashboardView`) and is opened on activation.
    """

    DOM_ELEMENT_CLASS = "panel-view"
    TEMPLATE_STR = '''
        <!-- Dashboard panel -->
        <div class="panel-head">
            <span data-i18n="tab_dashboard">Dashboard</span>
            <div class="panel-head-actions">
                <button class="panel-head-btn" onclick="pyview.refresh()" title="Refresh" aria-label="Refresh">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="panel-head-sub">Latest activity across chats, projects and work items.</div>
        <div class="insights-nav">
            <div class="insights-nav-item" onclick="pyview.openDashboard()">
                <span class="insights-nav-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg></span>
                <span class="insights-nav-text">
                    <span class="insights-nav-title">Overview</span>
                    <span class="insights-nav-desc">{{ pyview.chat_count }} chat(s) · {{ pyview.project_count }} project(s) · {{ pyview.workitem_count }} work item(s)</span>
                </span>
            </div>
            <div class="insights-nav-item" onclick="pyview.openChats()">
                <span class="insights-nav-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></span>
                <span class="insights-nav-text">
                    <span class="insights-nav-title">Chats</span>
                    <span class="insights-nav-desc">Latest conversations first.</span>
                </span>
            </div>
            <div class="insights-nav-item" onclick="pyview.openProjects()">
                <span class="insights-nav-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg></span>
                <span class="insights-nav-text">
                    <span class="insights-nav-title">Projects</span>
                    <span class="insights-nav-desc">Most recently active first.</span>
                </span>
            </div>
            <div class="insights-nav-item" onclick="pyview.openWorkItems()">
                <span class="insights-nav-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M8 4v16"/><path d="M16 4v16"/><path d="M3 10h18"/></svg></span>
                <span class="insights-nav-text">
                    <span class="insights-nav-title">Work items</span>
                    <span class="insights-nav-desc">{{ pyview.open_workitem_count }} open item(s) needing attention.</span>
                </span>
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: SidebarView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.root_view: UiAppView = parent.root_view

    @property
    def chat_count(self) -> int:
        try:
            from server.models.enums.session_enums import SessionType
            from server.models.sessions.session import SessionModel

            return SessionModel.objects.filter(
                parent_session__isnull=True,
                session_type=SessionType.SESSION,
                is_archived=False,
            ).count()
        except Exception:
            return 0

    @property
    def project_count(self) -> int:
        try:
            from server.models.project import Project

            return Project.objects.count()
        except Exception:
            return 0

    @property
    def workitem_count(self) -> int:
        try:
            from server.models.workitems.work_item import WorkItem

            return WorkItem.objects.count()
        except Exception:
            return 0

    @property
    def open_workitem_count(self) -> int:
        try:
            from server.models.workitems.work_item import WorkItem

            return WorkItem.objects.exclude(status__in=["done", "cancelled"]).count()
        except Exception:
            return 0

    def refresh(self) -> None:
        self.update()

    def openDashboard(self) -> None:
        from ui.main.dashboard.overview import GlobalDashboardView

        self.root_view.main_panel.create_and_open_tab(GlobalDashboardView, self.subject)

    def openChats(self) -> None:
        from ui.main.chat.overview import ChatsOverview

        self.root_view.main_panel.create_and_open_tab(ChatsOverview, self.subject)

    def openProjects(self) -> None:
        from ui.main.project.overview import ProjectsOverview

        self.root_view.main_panel.create_and_open_tab(ProjectsOverview, self.subject)

    def openWorkItems(self) -> None:
        from ui.main.workitems.board import WorkItemsBoard

        self.root_view.main_panel.create_and_open_tab(WorkItemsBoard, self.subject)

    def panel_activated(self) -> None:
        """Clicking the dashboard rail icon opens the global dashboard."""
        try:
            self.openDashboard()
        except Exception:
            pass
