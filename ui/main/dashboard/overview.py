"""Global dashboard — latest chats, projects and work items at a glance.

Opened from the dashboard rail/sidebar button (the topmost entry, above
chats). The right panel shows the global ``AgentOne`` main-agent sessions
(see :class:`RightPanelGlobalDashboard`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView

LATEST_CHAT_LIMIT = 8
LATEST_PROJECT_LIMIT = 6
LATEST_WORKITEM_LIMIT = 8


class GlobalDashboardView(ModelView):
    from ui.main.rightpanel.assistant_chat import RightPanelGlobalDashboard as RIGHTPANEL_VIEW

    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="ws-ov-topbar">
            <div class="ws-ov-breadcrumb">
                <span class="ws-ov-crumb">Dashboard</span>
            </div>
            <button class="ws-ov-primary" onclick="pyview.refresh()">Refresh</button>
        </div>
        <div class="main-view-body">
            <div class="main-view-content ws-ov-content">
                <div class="ws-ov-heading-row">
                    <div>
                        <h1 class="ws-ov-title">Dashboard</h1>
                        <div class="ws-ov-subtitle">Latest activity across chats, projects and work items.</div>
                    </div>
                </div>

                <div class="ws-sub-head ws-chat-head">
                    <h2 class="ws-sub-title">Latest chats <span class="ws-sub-count">{{ pyview.latest_chats|length }}</span></h2>
                    <button class="ws-ov-primary" onclick="pyview.openChats()">View all →</button>
                </div>
                <div class="ws-chat-list">
                    {% for c in pyview.latest_chats %}
                    <div class="ws-chat-row" onclick="pyview.openChat({{ c.pk }})">
                        {% if c.workspace_color %}<span class="ws-color-dot" style="background:{{ c.workspace_color }}" title="{{ c.workspace_name }}"></span>{% endif %}
                        <span class="ws-chat-name">{{ c.name }}</span>
                        <span class="ws-chat-type">{{ c.agent_name }}</span>
                        <span class="ws-chat-meta">{{ c.when }}</span>
                    </div>
                    {% endfor %}
                </div>
                {% if not pyview.latest_chats %}
                <div class="ws-ov-empty">
                    <h2>No chats yet</h2>
                    <div>Start one from the Chats panel.</div>
                </div>
                {% endif %}

                <div class="ws-sub-head ws-chat-head">
                    <h2 class="ws-sub-title">Latest projects <span class="ws-sub-count">{{ pyview.latest_projects|length }}</span></h2>
                    <button class="ws-ov-primary" onclick="pyview.openProjects()">View all →</button>
                </div>
                <div class="ws-ov-grid">
                    {% for project in pyview.latest_projects %}
                    <div class="ws-ov-card" onclick="pyview.openProject({{ project.pk }})">
                        <div class="ws-ov-card-top">
                            <div class="ws-ov-icon">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                            </div>
                            <h3>{{ project.name }}</h3>
                        </div>
                        <div class="ws-ov-card-info">
                            <div class="ws-ov-path" title="{{ project.path }}">{{ project.path }}</div>
                            <div class="ws-ov-desc">{{ project.description }}</div>
                        </div>
                        <div class="ws-ov-card-bottom">
                            <div class="ws-ov-status">
                                {{ project.agent_count }} agent(s) · {{ project.session_count }} chat(s)
                            </div>
                            <span>{{ project.when }}</span>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                {% if not pyview.latest_projects %}
                <div class="ws-ov-empty">
                    <h2>No projects yet</h2>
                    <div>Create one from the Projects panel.</div>
                </div>
                {% endif %}

                <div class="ws-sub-head ws-chat-head">
                    <h2 class="ws-sub-title">Latest work items <span class="ws-sub-count">{{ pyview.latest_workitems|length }}</span></h2>
                    <button class="ws-ov-primary" onclick="pyview.openWorkItems()">View all →</button>
                </div>
                <div class="ws-chat-list">
                    {% for w in pyview.latest_workitems %}
                    <div class="ws-chat-row" onclick="pyview.openWorkItem({{ w.pk }})">
                        <span class="ws-chat-type">{{ w.status_label }}</span>
                        <span class="ws-chat-name">{{ w.title }}</span>
                        <span class="ws-chat-meta">#{{ w.pk }} · {{ w.when }}</span>
                    </div>
                    {% endfor %}
                </div>
                {% if not pyview.latest_workitems %}
                <div class="ws-ov-empty">
                    <h2>No work items yet</h2>
                    <div>New items appear here as soon as they are created.</div>
                </div>
                {% endif %}
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    @staticmethod
    def _when(dt) -> str:
        if not dt:
            return ""
        try:
            from django.utils import timezone

            now = timezone.now()
            diff = now - dt
            secs = int(diff.total_seconds())
            if secs < 60:
                return "just now"
            mins = secs // 60
            if mins < 60:
                return f"{mins}m ago"
            hours = mins // 60
            if hours < 24:
                return f"{hours}h ago"
            days = hours // 24
            if days < 7:
                return f"{days}d ago"
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return ""

    @property
    def latest_chats(self) -> list[dict]:
        from server.models.enums.session_enums import SessionType
        from server.models.sessions.session import SessionModel

        try:
            sessions = list(
                SessionModel.objects.filter(
                    parent_session__isnull=True,
                    session_type=SessionType.SESSION,
                    is_archived=False,
                )
                .select_related("latest_session_version__agent", "latest_session_version__workspace")
                .order_by("-updated_at")[:LATEST_CHAT_LIMIT]
            )
        except Exception:
            return []
        rows = []
        for s in sessions:
            try:
                sv = s.latest_session_version
                agent_name = getattr(getattr(sv, "agent", None), "name", "") or ""
                ws = getattr(sv, "workspace", None)
                ws_color = getattr(ws, "color", "") or ""
                ws_name = getattr(ws, "name", "") or ""
            except Exception:
                agent_name, ws_color, ws_name = "", "", ""
            rows.append({
                "pk": s.pk,
                "name": s.name or f"Session {s.pk}",
                "agent_name": agent_name,
                "workspace_color": ws_color,
                "workspace_name": ws_name,
                "when": self._when(getattr(s, "updated_at", None)),
            })
        return rows

    @property
    def latest_projects(self) -> list[dict]:
        from server.models.project import Project
        from ui.main.project.overview import project_card_data

        try:
            projects = list(Project.objects.all().order_by("-updated_at")[:LATEST_PROJECT_LIMIT])
        except Exception:
            return []
        rows = []
        for p in projects:
            card = project_card_data(p)
            card["when"] = self._when(getattr(p, "updated_at", None))
            rows.append(card)
        return rows

    @property
    def latest_workitems(self) -> list[dict]:
        from server.models.workitems.work_item import WorkItem
        from ui.main.workitems.board_data import STATUS_COLUMNS

        labels = dict(STATUS_COLUMNS)
        try:
            items = list(WorkItem.objects.all().order_by("-updated_at")[:LATEST_WORKITEM_LIMIT])
        except Exception:
            return []
        return [{
            "pk": w.pk,
            "title": getattr(w, "title", "") or f"Work item {w.pk}",
            "status_label": labels.get(getattr(w, "status", ""), getattr(w, "status", "?")),
            "when": self._when(getattr(w, "updated_at", None)),
        } for w in items]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self.update()

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent

    def openChat(self, pk: int) -> None:
        from ui.main.chat.chat import Chat
        from server.models.sessions.session import SessionModel

        try:
            session = SessionModel.objects.get(pk=int(pk))
        except (SessionModel.DoesNotExist, ValueError, TypeError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(Chat, session)

    def openChats(self) -> None:
        from ui.main.chat.overview import ChatsOverview

        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(ChatsOverview, self.subject)

    def openProject(self, pk: int) -> None:
        from server.models.project import Project
        from ui.main.project.project_view import ProjectView

        try:
            project = Project.objects.get(pk=int(pk))
        except (Project.DoesNotExist, ValueError, TypeError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(ProjectView, project)

    def openProjects(self) -> None:
        from ui.main.project.overview import ProjectsOverview

        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(ProjectsOverview, self.subject)

    def openWorkItem(self, pk: int) -> None:
        from ui.main.workitems.board import WorkItemsBoard

        main_view = self._find_main_view()
        if main_view is not None:
            board = main_view.create_and_open_tab(WorkItemsBoard, self.subject)
            try:
                board.select(int(pk))
            except (ValueError, TypeError, AttributeError):
                pass

    def openWorkItems(self) -> None:
        from ui.main.workitems.board import WorkItemsBoard

        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(WorkItemsBoard, self.subject)
