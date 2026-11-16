"""Cron jobs: overview, detail, create, edit, duplicate, delete and run."""

from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.agents.agent import AgentModel
from server.models.cron import Cronjob
from server.models.project import Project
from server.models.workspace import WorkspaceModel
from runtime.cron.content import build_cron_message
from runtime.cron.execute import execute_cron_job
from runtime.cron.file_io import (
    delete_cron_file,
    rename_cron_file,
    write_cron_file,
)
from runtime.cron.schedule import compute_next_run
from webui.core.assistants import assistant_overview_context, assistant_panel_context
from webui.core.shell import render_page

log = logging.getLogger(__name__)

_FUNCTION_TYPES = ("task", "tool", "command")


def _agent(raw: str) -> AgentModel | None:
    return AgentModel.objects.filter(pk=int(raw)).first() if raw.isdigit() else None


def _project(raw: str) -> Project | None:
    return Project.objects.filter(pk=int(raw)).first() if raw.isdigit() else None


def _workspace(raw: str) -> WorkspaceModel | None:
    return WorkspaceModel.objects.filter(pk=int(raw)).first() if raw.isdigit() else None


def _function_fields(request) -> tuple[str, str]:
    function_type = (request.POST.get("function_type") or "").strip()
    function_name = (request.POST.get("function_name") or "").strip()
    if function_type not in _FUNCTION_TYPES:
        return "", ""
    if not function_name:
        return function_type, ""
    return function_type, function_name


def _apply_form(cron: Cronjob, request) -> str | None:
    """Copy POST fields onto *cron*; return an error code or ``None``."""
    schedule = (request.POST.get("schedule") or "").strip()
    agent = _agent(request.POST.get("agent", ""))
    if not schedule or compute_next_run(schedule) is None:
        return "invalid"
    if agent is None:
        return "invalid"

    function_type, function_name = _function_fields(request)
    if function_type and not function_name:
        return "function"
    try:
        message = build_cron_message(request.POST.get("message") or "", function_type)
    except ValueError:
        return "json"

    cron.name = (request.POST.get("name") or "").strip() or f"cron-{agent.name}"
    cron.schedule = schedule
    cron.agent = agent
    cron.parent_project = _project(request.POST.get("parent_project", ""))
    cron.workspace = _workspace(request.POST.get("workspace", ""))
    cron.session_mode = (
        "existing" if request.POST.get("session_mode") == "existing" else "new"
    )
    cron.session_name = (request.POST.get("session_name") or "").strip()
    cron.description = (request.POST.get("description") or "").strip()
    cron.function_type = function_type
    cron.function_name = function_name
    cron.message = message
    return None


def cronjobs(request):
    rows = list(
        Cronjob.objects.filter(is_archived=False)
        .select_related("agent", "parent_project", "workspace")
        .order_by("-is_active", "name")
    )
    context = {
        "cronjobs": rows,
        "agents": list(
            AgentModel.objects.filter(is_archived=False).order_by("name")
        ),
        "projects": list(Project.objects.order_by("name")),
        "workspaces": list(WorkspaceModel.objects.order_by("name")),
        "error": request.GET.get("error", ""),
    }
    context.update(assistant_overview_context("cronjobs"))
    return render_page(request, "cron", "cron/list.html", context)


@require_POST
def cron_create(request):
    cron = Cronjob()
    error = _apply_form(cron, request)
    if error:
        return redirect(f"/app/cron?error={error}")
    cron.save()
    write_cron_file(cron)
    return redirect("webui:cronjob", cron_id=cron.pk)


def cron_detail(request, cron_id: int):
    cron = get_object_or_404(
        Cronjob.objects.select_related("agent", "parent_project", "workspace"),
        pk=cron_id,
    )
    context = {
        "cron": cron,
        "message": cron.message.get() if cron.message is not None else "",
        "calls": list(
            cron.related_task_calls.select_related("session").order_by("-pk")[:40]
        ),
        "agents": list(AgentModel.objects.filter(is_archived=False).order_by("name")),
        "workspaces": list(WorkspaceModel.objects.order_by("name")),
        "projects": list(Project.objects.order_by("name")),
        "error": request.GET.get("error", ""),
    }
    context.update(assistant_panel_context("cron", cron, request.GET.get("assistant_session")))
    return render_page(request, "cron", "cron/detail.html", context,
                       active_id=cron.pk)


@require_POST
def cron_edit(request, cron_id: int):
    cron = get_object_or_404(Cronjob, pk=cron_id)
    old_name = cron.name
    old_project = cron.parent_project
    old_manifest_dir = cron.manifest_dir
    error = _apply_form(cron, request)
    if error:
        return redirect(f"/app/cron/{cron.pk}?error={error}")
    cron.save()
    if cron.name != old_name:
        rename_cron_file(old_name, cron.name, old_project, old_manifest_dir)
    write_cron_file(cron)
    return redirect("webui:cronjob", cron_id=cron.pk)


@require_POST
def cron_toggle(request, cron_id: int):
    cron = get_object_or_404(Cronjob, pk=cron_id)
    cron.is_active = not cron.is_active
    cron.save(update_fields=["is_active"])
    write_cron_file(cron)
    return redirect("webui:cronjob", cron_id=cron.pk)


@require_POST
def cron_duplicate(request, cron_id: int):
    source = get_object_or_404(Cronjob, pk=cron_id)
    base = f"{source.name}-copy"
    name = base
    index = 2
    while Cronjob.objects.filter(name=name, parent_project=source.parent_project).exists():
        name = f"{base}{index}"
        index += 1

    text = source.message.get() if source.message is not None else ""
    try:
        message = build_cron_message(text, source.function_type)
    except ValueError:
        message = None

    cron = Cronjob(
        name=name,
        description=source.description,
        schedule=source.schedule,
        agent=source.agent,
        parent_project=source.parent_project,
        workspace=source.workspace,
        session_mode=source.session_mode,
        session_name=source.session_name,
        function_type=source.function_type,
        function_name=source.function_name,
        message=message,
    )
    cron.save()
    write_cron_file(cron)
    return redirect("webui:cronjob", cron_id=cron.pk)


@require_POST
def cron_delete(request, cron_id: int):
    cron = get_object_or_404(Cronjob, pk=cron_id)
    delete_cron_file(cron.name, cron.parent_project, cron.manifest_dir)
    cron.delete()
    return redirect("webui:cron")


@require_POST
def cron_run_now(request, cron_id: int):
    cron = get_object_or_404(Cronjob, pk=cron_id)
    try:
        execute_cron_job(cron.pk)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("cron run-now failed for %s", cron.pk)
        return redirect(f"/app/cron/{cron.pk}?error=run")
    return redirect("webui:cronjob", cron_id=cron.pk)


@require_POST
def cron_call_cancel(request, cron_id: int, call_id: int):
    """Stop a waiting or active execution belonging to this cron job."""
    cron = get_object_or_404(Cronjob, pk=cron_id)
    call = get_object_or_404(AgentTaskCall, pk=call_id, cronjob=cron)
    if call.status != "ENDED":
        from server.tasks.recovery_scheduler import _force_end_call

        try:
            _force_end_call(call)
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("could not cancel cron call %s for cron %s", call_id, cron_id)
            return redirect(f"/app/cron/{cron.pk}?error=cancel")
    return redirect("webui:cronjob", cron_id=cron.pk)
