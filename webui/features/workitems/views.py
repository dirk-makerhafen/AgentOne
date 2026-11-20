"""Work items: kanban board, detail, create, edit, FSM actions and delete."""

from __future__ import annotations

from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from server.models.agents.agent import AgentModel
from server.models.project import Project
from server.models.workitems.enums import WorkItemStatus
from server.models.workitems.work_item import WorkItem
from webui.features.workitems.board import (
    STATUS_COLUMNS,
    actions_for,
    agent_filter_options,
    apply_action,
    count_by_status,
    group_by_status,
    item_row,
    scoped_queryset,
    status_label,
)
from webui.core.assistants import assistant_overview_context
from webui.core.components import render_fragment
from webui.core.layout import render_page

_ACTIONABLE_STATUSES = ("in_review", "blocked", "ready")


def _filter_rows(rows: list[dict], request) -> list[dict]:
    agent_filter = (request.GET.get("assignee") or "").strip()
    verify_filter = (request.GET.get("verify") or "").strip()
    only_actionable = request.GET.get("actionable") == "1"

    if agent_filter:
        rows = [row for row in rows if (row["assignee"] or "") == agent_filter]
    if verify_filter == "required":
        rows = [row for row in rows if row["requires_verification"]]
    elif verify_filter == "pending":
        rows = [row for row in rows if row["verify_status"] in ("", "pending")]
    elif verify_filter:
        rows = [row for row in rows if row["verify_status"] == verify_filter]
    if only_actionable:
        rows = [row for row in rows if row["status"] in _ACTIONABLE_STATUSES]
    return rows


def _board_context(request) -> dict:
    raw_project = request.GET.get("project", "")
    project_id = int(raw_project) if raw_project.isdigit() else None
    show_terminal = request.GET.get("terminal") == "1"

    items = [
        item_row(item)
        for item in scoped_queryset(project_id, include_terminal=show_terminal)
    ]
    if not show_terminal:
        items = [
            row
            for row in items
            if row["status"] not in (WorkItemStatus.DONE, WorkItemStatus.CANCELLED)
        ]
    items = _filter_rows(items, request)
    for row in items:
        row["actions"] = actions_for(row)

    scope_label = "All projects"
    if project_id is not None:
        scope_label = (
            Project.objects.filter(pk=project_id)
            .values_list("name", flat=True)
            .first()
            or scope_label
        )

    return {
        "columns": [{"value": value, "label": label} for value, label in STATUS_COLUMNS],
        "grouped": group_by_status(items),
        "counts": count_by_status(items),
        "total": len(items),
        "project_id": project_id,
        "show_terminal": show_terminal,
        "agent_filter": (request.GET.get("assignee") or "").strip(),
        "verify_filter": (request.GET.get("verify") or "").strip(),
        "only_actionable": request.GET.get("actionable") == "1",
        "assignee_options": agent_filter_options(project_id),
        "scope_label": scope_label,
        "projects": list(Project.objects.order_by("name")),
        "agent_options": [
            {"id": agent.pk, "label": agent.name}
            for agent in AgentModel.objects.filter(is_archived=False).order_by("name")
        ],
        "board_qs": _board_qs(request),
    }


def _board_qs(request) -> str:
    from urllib.parse import urlencode

    params: list[tuple[str, str]] = []
    for key in ("project", "assignee", "verify"):
        value = request.GET.get(key)
        if value:
            params.append((key, value))
    if request.GET.get("terminal") == "1":
        params.append(("terminal", "1"))
    if request.GET.get("actionable") == "1":
        params.append(("actionable", "1"))
    return urlencode(params)


def workitems(request):
    context = _board_context(request)
    project = (
        Project.objects.filter(pk=context["project_id"]).first()
        if context["project_id"] is not None
        else None
    )
    context.update(assistant_overview_context("workitems", project))
    return render_page(request, "workitems", "workitems/board.html", context)


def workitems_board(request):
    """Live-refreshed kanban columns.

    htmx asks for this as a fragment; a direct visit (new tab, bookmark)
    gets the full page instead of a bare board.
    """
    if request.headers.get("HX-Request") != "true":
        return workitems(request)
    return render_fragment(
        request, "workitems/parts/board.html", _board_context(request)
    )


def workitem_detail(request, workitem_id: int):
    item = get_object_or_404(
        WorkItem.objects.select_related(
            "project", "assigned_agent", "executor_session", "parent"
        ),
        pk=workitem_id,
    )
    row = item_row(item)
    context = {
        "item": item,
        "row": row,
        "actions": actions_for(row),
        "children": list(item.child_items.order_by("-priority", "created_at")),
        "projects": list(Project.objects.order_by("name")),
        "agents": list(AgentModel.objects.filter(is_archived=False).order_by("name")),
    }
    context.update(assistant_overview_context("workitems", item.project))
    return render_page(request, "workitems", "workitems/detail.html", context,
                       active_id=item.pk)


@require_POST
def workitem_create(request):
    title = (request.POST.get("title") or "").strip()
    if not title:
        return redirect("webui:workitems")

    raw_project = request.POST.get("project", "")
    project = (
        Project.objects.filter(pk=int(raw_project)).first()
        if raw_project.isdigit()
        else None
    )
    raw_agent = request.POST.get("assigned_agent", "")
    agent = (
        AgentModel.objects.filter(pk=int(raw_agent)).first()
        if raw_agent.isdigit()
        else None
    )
    try:
        priority = int(request.POST.get("priority") or 99)
    except ValueError:
        priority = 99

    item = WorkItem.objects.create(
        title=title,
        body=(request.POST.get("body") or "").strip(),
        project=project,
        assigned_agent=agent,
        priority=priority,
        requires_verification=request.POST.get("requires_verification") == "on",
    )
    return redirect("webui:workitem", workitem_id=item.pk)


@require_POST
def workitem_action(request, workitem_id: int):
    action = (request.POST.get("action") or "").strip()
    reason = (request.POST.get("reason") or "").strip()
    apply_action(workitem_id, action, reason)
    target = request.POST.get("next") or ""
    if target.startswith("/app/"):
        return redirect(target)
    return redirect("webui:workitem", workitem_id=workitem_id)


@require_POST
def workitem_update(request, workitem_id: int):
    item = get_object_or_404(WorkItem, pk=workitem_id)
    title = (request.POST.get("title") or "").strip()
    if title:
        item.title = title
    item.body = (request.POST.get("body") or "").strip()
    raw_project = request.POST.get("project", "")
    item.project = (
        Project.objects.filter(pk=int(raw_project)).first()
        if raw_project.isdigit()
        else None
    )
    raw_agent = request.POST.get("assigned_agent", "")
    item.assigned_agent = (
        AgentModel.objects.filter(pk=int(raw_agent)).first()
        if raw_agent.isdigit()
        else None
    )
    try:
        item.priority = int(request.POST.get("priority") or item.priority)
    except ValueError:
        pass
    item.requires_verification = request.POST.get("requires_verification") == "on"
    item.save()
    return redirect("webui:workitem", workitem_id=item.pk)


@require_POST
def workitem_delete(request, workitem_id: int):
    item = get_object_or_404(WorkItem, pk=workitem_id)
    project_id = item.project_id
    item.delete()
    if project_id is not None:
        return redirect(f"/app/workitems?project={project_id}")
    return redirect("webui:workitems")


def workitem_status_label(status: str) -> str:
    return status_label(status)
