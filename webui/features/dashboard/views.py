"""Dashboard and the full conversation list."""

from __future__ import annotations

from django.db.models import Count, Q

from server.models.agents.agent import AgentModel
from server.models.cron import Cronjob
from server.models.enums.session_enums import SessionType
from server.models.project import Project
from server.models.sessions.session import SessionModel
from server.models.workitems.enums import WorkItemStatus
from server.models.workitems.work_item import WorkItem
from server.models.workspace import WorkspaceModel
from webui.core.assistants import assistant_overview_context
from webui.core.shell import render_page, sidebar_sessions


def dashboard(request):
    """Landing page: overview + recent conversations + quick links."""
    open_work = WorkItem.objects.exclude(
        status__in=[WorkItemStatus.DONE, WorkItemStatus.CANCELLED]
    )
    context = {
        "error": request.GET.get("error", ""),
        "sessions": sidebar_sessions(limit=10),
        "stats": {
            "chats": SessionModel.objects.filter(
                parent_session__isnull=True,
                session_type=SessionType.SESSION,
                is_archived=False,
            ).count(),
            "agents": AgentModel.objects.filter(is_archived=False).count(),
            "projects": Project.objects.count(),
            "open_work": open_work.count(),
            "cron_active": Cronjob.objects.filter(
                is_active=True, is_archived=False
            ).count(),
        },
        "recent_work": list(
            open_work.select_related("assigned_agent").order_by("-priority", "-pk")[:8]
        ),
        "latest_projects": list(
            Project.objects.annotate(
                agent_count=Count("child_agents", distinct=True),
                session_count=Count("child_sessions", distinct=True),
            ).order_by("-updated_at")[:6]
        ),
    }
    context.update(assistant_overview_context("dashboard"))
    return render_page(request, "dashboard", "dashboard/single.html", context)


def chats(request):
    """All conversations, including archived ones."""
    show_archived = request.GET.get("archived") == "1"
    query = (request.GET.get("q") or "").strip()
    qs = (
        SessionModel.objects.filter(
            parent_session__isnull=True,
            session_type=SessionType.SESSION,
            is_archived=show_archived,
        )
        .select_related("latest_session_version__agent", "parent_project")
        .annotate(
            message_count=Count("related_messages", distinct=True),
        )
        .order_by("-is_pinned", "-last_active_at", "-created_at")
    )
    if query:
        qs = qs.filter(Q(name__icontains=query))
    context = {
        "sessions": list(qs[:300]),
        "show_archived": show_archived,
        "q": query,
        "agents": [
            agent
            for agent in AgentModel.objects.filter(is_archived=False).order_by("name")
            if agent.is_user_visible
        ],
        "workspaces": list(
            WorkspaceModel.objects.order_by("name")
        ),
        "archived_count": SessionModel.objects.filter(
            parent_session__isnull=True,
            session_type=SessionType.SESSION,
            is_archived=True,
        ).count(),
    }
    return render_page(request, "chats", "chats/list.html", context)
