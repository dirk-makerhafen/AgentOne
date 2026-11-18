"""Sidebar data and component registration for the chats section."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from server.models.enums.session_enums import SessionType
from server.models.sessions.session import SessionModel

log = logging.getLogger(__name__)

SIDEBAR_LIMIT = 80
RECENT_SUBSESSION_WINDOW = timedelta(minutes=30)
MAX_INACTIVE_SUBSESSIONS = 5
SESSION_TREE_MAX_DEPTH = 8
_CHILD_SESSION_TYPES = (
    SessionType.SESSION,
    #SessionType.CRONJOB,
    #SessionType.SUBSESSION,
    #SessionType.SUBTASK_COMPACT,
    #SessionType.SUBTASK_DELEGATE,
)


def sidebar_sessions(limit: int = SIDEBAR_LIMIT) -> list[SessionModel]:
    """Top-level user conversations, pinned first."""
    return list(
        SessionModel.objects.filter(
            parent_session__isnull=True,
            is_archived=False,
            session_type=SessionType.SESSION,
        )
        .select_related(
            "latest_session_version__agent",
            "latest_session_version__workspace",
            "parent_project",
        )
        .order_by("-is_pinned", "-last_active_at", "-created_at")[:limit]
    )


def _visible_child_sessions(
    parents: list[SessionModel], include_archived: bool
) -> dict[int, list[SessionModel]]:
    ids = [parent.pk for parent in parents if parent.pk is not None]
    if not ids:
        return {}
    cutoff = timezone.now() - RECENT_SUBSESSION_WINDOW
    query = SessionModel.objects.filter(
        parent_session_id__in=ids,
        session_type__in=_CHILD_SESSION_TYPES,
    ).filter(Q(is_active=True) | Q(last_active_at__gte=cutoff))
    if not include_archived:
        query = query.filter(is_archived=False)
    query = query.select_related(
        "latest_session_version__agent",
        "latest_session_version__workspace",
        "parent_project",
    ).order_by("-created_at")

    grouped: dict[int, list[SessionModel]] = {}
    for child in query:
        grouped.setdefault(child.parent_session_id, []).append(child)

    result: dict[int, list[SessionModel]] = {}
    for parent_id, children in grouped.items():
        active = [child for child in children if child.is_active]
        inactive = [child for child in children if not child.is_active]
        inactive = sorted(
            inactive,
            key=lambda child: child.last_active_at or child.created_at,
            reverse=True,
        )[:MAX_INACTIVE_SUBSESSIONS]
        result[parent_id] = sorted(
            active + inactive,
            key=lambda child: child.created_at,
            reverse=True,
        )
    return result


def attach_session_children(
    sessions: list[SessionModel], include_archived: bool = False
) -> list[SessionModel]:
    def recurse(nodes: list[SessionModel], depth: int) -> None:
        for node in nodes:
            node.children = []
            node.tree_depth = depth
        if depth >= SESSION_TREE_MAX_DEPTH:
            return
        grouped = _visible_child_sessions(nodes, include_archived)
        for node in nodes:
            children = grouped.get(node.pk, [])
            node.children = children
            recurse(children, depth + 1)

    recurse(sessions, 0)
    return sessions


def flatten_session_tree(sessions: list[SessionModel]):
    for session in sessions:
        yield session
        yield from flatten_session_tree(getattr(session, "children", []) or [])


def session_activity(sessions: list[SessionModel]) -> dict:
    ids = [session.pk for session in sessions]
    if not ids:
        return {"active_session_ids": set(), "approval_session_ids": set()}
    from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
    from server.models.queries.query import Query, QueryStatus
    from server.models.tasks.agent_task_call import AgentTaskCall

    try:
        active = set(
            Query.objects.filter(
                session_version__session_id__in=ids,
                status=QueryStatus.ACTIVE,
            ).values_list("session_version__session_id", flat=True)
        )
        active |= set(
            AgentTaskCall.objects.filter(session_id__in=ids)
            .exclude(status=TaskCallStatus.ENDED)
            .values_list("session_id", flat=True)
            .distinct()
        )
        approval = set(
            AgentTaskCall.objects.filter(
                session_id__in=ids,
                requires_approval=True,
                status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
            ).values_list("session_id", flat=True)
        )
    except Exception:  # pylint: disable=broad-exception-caught
        return {"active_session_ids": set(), "approval_session_ids": set()}
    return {"active_session_ids": active, "approval_session_ids": approval}


def visible_child_session_ids(parent_id: int, *, include_archived: bool) -> list[int]:
    cutoff = timezone.now() - RECENT_SUBSESSION_WINDOW
    query = SessionModel.objects.filter(
        parent_session_id=parent_id,
        session_type__in=_CHILD_SESSION_TYPES,
    ).filter(Q(is_active=True) | Q(last_active_at__gte=cutoff))
    if not include_archived:
        query = query.filter(is_archived=False)
    children = list(query.order_by("-created_at").values("pk", "is_active", "last_active_at", "created_at"))
    active = [c for c in children if c["is_active"]]
    inactive = [c for c in children if not c["is_active"]]
    inactive = sorted(
        inactive,
        key=lambda c: c["last_active_at"] or c["created_at"],
        reverse=True,
    )[:MAX_INACTIVE_SUBSESSIONS]
    selected = sorted(active + inactive, key=lambda c: c["created_at"], reverse=True)
    return [c["pk"] for c in selected]


def build_sidebar_context(request, project_id, ctx):
    show_archived = request.GET.get("archived") == "1"
    query = (request.GET.get("q") or "").strip()
    qs = SessionModel.objects.filter(
        parent_session__isnull=True,
        session_type=SessionType.SESSION,
        is_archived=show_archived,
    ).select_related(
        "latest_session_version__agent",
        "latest_session_version__workspace",
        "parent_project",
    )
    if project_id is not None:
        qs = qs.filter(parent_project_id=project_id)
    if query:
        qs = qs.filter(Q(name__icontains=query))
    sessions = list(
        qs.order_by("-is_pinned", "-last_active_at", "-created_at")[:SIDEBAR_LIMIT]
    )
    ctx["sidebar_sessions"] = sessions
    ctx["show_archived"] = show_archived
    ctx["archived_flag"] = "true" if show_archived else "false"
    ctx["q"] = query
    ctx["subagent_count"] = SessionModel.objects.filter(
        parent_session__isnull=False,
        is_active=True,
        session_type=SessionType.SESSION,
    ).count()
    ctx["projects"] = ctx["sidebar_projects"]


def sidebar_keys(context):
    archived = "true" if context.get("show_archived") else "false"
    keys = [
        f"SessionModel.root@is_archived:{archived}",
        "SessionModel@is_active:true",
        "Query",
        "AgentTaskCall",
        "Project.root",
    ]
    project_id = context.get("sidebar_project_id")
    if project_id:
        keys.append(f"SessionModel.root@project:{project_id}@is_archived:{archived}")
    return tuple(keys)


def register_sidebar_component(section="chats"):
    from webui.core.components import register_section_sidebar

    register_section_sidebar(section, sidebar_keys)
