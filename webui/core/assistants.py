"""Assistant launch and scope helpers for entity detail pages."""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from server.models.agents.agent import AgentModel
from server.models.cron import Cronjob
from server.models.project import Project
from server.models.sessions.session import SessionModel
from server.models.skills.skill import SkillModel
from server.models.workspace import WorkspaceModel
from webui.core.shell import unique_session_name

log = logging.getLogger(__name__)

_ASSISTANTS = {
    "agent": ("agent_assistant", AgentModel),
    "skill": ("skill_assistant", SkillModel),
    "cron": ("cronjob_assistant", Cronjob),
    "project": ("project_assistant", Project),
    "workspace": ("workspace_assistant", WorkspaceModel),
}

_OVERVIEW_ASSISTANTS = {
    "dashboard": ("AgentOne", "AgentOne"),
    "agents": ("agents_assistant", "Agents assistant"),
    "projects": ("projects_assistant", "Projects assistant"),
    "workspaces": ("workspaces_assistant", "Workspaces assistant"),
    "cronjobs": ("cronjobs_assistant", "Cron assistant"),
    "workitems": ("workitems_assistant", "Work items assistant"),
}


def _assistant_scope(kind: str, item):
    assistant_name, _model = _ASSISTANTS[kind]
    if kind == "agent":
        from runtime.agents.agent import Agent

        runtime = Agent(agent_model=item)
    elif kind == "skill":
        from runtime.skill.skill import Skill

        runtime = Skill(skill_model=item)
    elif kind == "cron":
        from runtime.cron.cron import Cron

        runtime = Cron(cronjob_model=item)
    elif kind == "project":
        from runtime.project.project import Project as ProjectRuntime

        runtime = ProjectRuntime(project_model=item)
    else:
        from runtime.workspace.workspace import Workspace

        runtime = Workspace(workspace_model=item)
    project = item if kind == "project" else getattr(item, "parent_project", None)
    if kind == "cron":
        project = item.parent_project
    workspace = runtime.get_assistant_workspace()
    if project is None and workspace is not None:
        project = getattr(workspace, "parent_project", None)
    return assistant_name, project, workspace


def _overview_scope(kind: str, project: Project | None):
    """Resolve the runtime workspace/project binding for a collection assistant."""
    assistant_name, _title = _OVERVIEW_ASSISTANTS[kind]
    if kind == "dashboard":
        from runtime.workspace.workspaces import Workspaces

        return assistant_name, None, Workspaces().get_assistant_workspace()

    from runtime.agents.agents import Agents
    from runtime.cron.crons import Cronjobs
    from runtime.project.projects import Projects
    from runtime.workitems.workitems import Workitems
    from runtime.workspace.workspaces import Workspaces

    collections = {
        "agents": Agents,
        "projects": Projects,
        "workspaces": Workspaces,
        "cronjobs": Cronjobs,
        "workitems": Workitems,
    }
    collection_type = collections[kind]
    try:
        collection = collection_type(parent_project=project)
    except TypeError:
        collection = collection_type()
    workspace = collection.get_assistant_workspace()
    if project is None and workspace is not None:
        project = getattr(workspace, "parent_project", None)
    return assistant_name, project, workspace


def _sessions_for_scope(
    assistant_name: str, project: Project | None, workspace
) -> list[SessionModel]:
    return list(
        SessionModel.objects.filter(
            latest_session_version__agent__name=assistant_name,
            latest_session_version__workspace=workspace,
            parent_project=project,
        )
        .select_related("latest_session_version__agent")
        .order_by("-created_at")[:20]
    )


def assistant_sessions(kind: str, item) -> list[SessionModel]:
    """Return assistant chats bound to the entity's exact runtime scope."""
    assistant_name, project, workspace = _assistant_scope(kind, item)
    return _sessions_for_scope(assistant_name, project, workspace)


def assistant_panel_context(kind: str, item, selected_id: str | None = None) -> dict:
    """Build the scoped embedded-chat panel context for an entity detail page."""
    sessions = assistant_sessions(kind, item)
    selected = next(
        (session for session in sessions if str(session.pk) == str(selected_id)),
        sessions[0] if sessions else None,
    )
    context = {
        "assistant_kind": kind,
        "assistant_title": f"{kind.title()} assistant",
        "assistant_item": item,
        "assistant_sessions": sessions,
        "assistant_session": selected,
        "assistant_error": "",
        "assistant_panel_url": reverse(
            "webui:assistant_panel", args=[kind, item.pk]
        ),
        "assistant_open_url": reverse(
            "webui:entity_assistant_open", args=[kind, item.pk]
        ),
    }
    if selected is not None:
        from webui.core.shell import session_context

        context.update(session_context(selected, limit=40))
    return context


def _requested_project(request):
    raw_project = request.GET.get("project") or request.POST.get("project", "")
    if not raw_project:
        return None
    if not raw_project.isdigit():
        raise ValueError("Invalid project scope.")
    return get_object_or_404(Project, pk=int(raw_project))


def assistant_overview_context(
    kind: str, project: Project | None = None, selected_id: str | None = None
) -> dict:
    """Build the panel context for a legacy collection/dashboard assistant."""
    assistant_name, title = _OVERVIEW_ASSISTANTS[kind]
    assistant_name, project, workspace = _overview_scope(kind, project)
    sessions = _sessions_for_scope(assistant_name, project, workspace)
    selected = next(
        (session for session in sessions if str(session.pk) == str(selected_id)),
        sessions[0] if sessions else None,
    )
    panel_url = reverse("webui:assistant_overview_panel", args=[kind])
    if project is not None:
        panel_url = f"{panel_url}?{urlencode({'project': project.pk})}"
    context = {
        "assistant_kind": kind,
        "assistant_title": title,
        "assistant_item": {"name": project.name if project else "All scopes"},
        "assistant_sessions": sessions,
        "assistant_session": selected,
        "assistant_error": "",
        "assistant_panel_url": panel_url,
        "assistant_open_url": reverse("webui:assistant_overview_open", args=[kind]),
        "assistant_project_id": project.pk if project else "",
    }
    if selected is not None:
        from webui.core.shell import session_context

        context.update(session_context(selected, limit=40))
    return context


@require_GET
def assistant_panel(request, kind: str, item_id: int):
    """Return the embedded assistant panel, optionally selecting a session."""
    if kind not in _ASSISTANTS:
        return redirect("/app/")
    _assistant_name, model = _ASSISTANTS[kind]
    item = get_object_or_404(model, pk=item_id)
    context = assistant_panel_context(kind, item, request.GET.get("session", ""))
    return render(request, "shared/_assistant_panel.html", context)


@require_GET
def assistant_overview_panel(request, kind: str):
    """Return an overview assistant panel, optionally selecting a session."""
    if kind not in _OVERVIEW_ASSISTANTS:
        return HttpResponse("Unknown assistant scope.", status=404)
    try:
        project = _requested_project(request)
        context = assistant_overview_context(
            kind, project, request.GET.get("session", "")
        )
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    return render(request, "shared/_assistant_panel.html", context)


@require_POST
def entity_assistant_open(request, kind: str, item_id: int):
    """Create and open a fresh assistant session for an entity."""
    if kind not in _ASSISTANTS:
        return redirect("/app/")
    assistant_name, model = _ASSISTANTS[kind]
    item = get_object_or_404(model, pk=item_id)
    try:
        assistant_name, project, workspace = _assistant_scope(kind, item)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not resolve %s assistant scope for %s", kind, item_id)
        if request.headers.get("HX-Request") == "true":
            return render(request, "shared/_assistant_panel.html", {
                "assistant_kind": kind,
                "assistant_title": f"{kind.title()} assistant",
                "assistant_item": item,
                "assistant_sessions": [],
                "assistant_panel_url": reverse(
                    "webui:assistant_panel", args=[kind, item.pk]
                ),
                "assistant_open_url": reverse(
                    "webui:entity_assistant_open", args=[kind, item.pk]
                ),
                "assistant_error": "Could not resolve this assistant scope.",
            })
        return redirect(f"/app/{_detail_path(kind)}/{item.pk}?error=assistant-scope")

    assistant = AgentModel.objects.filter(name=assistant_name).first()
    if assistant is None or assistant.latest_agent_version is None:
        if request.headers.get("HX-Request") == "true":
            context = assistant_panel_context(kind, item)
            context["assistant_error"] = "This assistant is unavailable."
            return render(request, "shared/_assistant_panel.html", context)
        return redirect(f"/app/{_detail_path(kind)}/{item.pk}?error=assistant-unavailable")

    base_name = f"{assistant_name} - {item.name}"
    name = unique_session_name(base_name)
    try:
        session_version = assistant.latest_agent_version.get_or_create_session(
            name=name,
            display_name=name,
            description="",
            workspace=workspace,
            group_key=f"assistant:{assistant_name}",
        )
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not create %s assistant chat for %s", kind, item_id)
        if request.headers.get("HX-Request") == "true":
            context = assistant_panel_context(kind, item)
            context["assistant_error"] = "Could not create an assistant chat."
            return render(request, "shared/_assistant_panel.html", context)
        return redirect(f"/app/{_detail_path(kind)}/{item.pk}?error=assistant-create")

    session = session_version.session
    if project is not None and session.parent_project_id != project.pk:
        session.parent_project = project
        session.save(update_fields=["parent_project_id"])
    if request.headers.get("HX-Request") == "true":
        context = assistant_panel_context(kind, item, str(session.pk))
        return render(request, "shared/_assistant_panel.html", context)
    return redirect("webui:chat", session_id=session.pk)


@require_POST
def assistant_overview_open(request, kind: str):
    """Create a collection/dashboard-scoped assistant chat in-place."""
    if kind not in _OVERVIEW_ASSISTANTS:
        return HttpResponse("Unknown assistant scope.", status=404)
    try:
        project = _requested_project(request)
        assistant_name, project, workspace = _overview_scope(kind, project)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not resolve %s assistant scope", kind)
        return HttpResponse("Could not resolve this assistant scope.", status=500)

    assistant = AgentModel.objects.filter(name=assistant_name).first()
    if assistant is None or assistant.latest_agent_version is None:
        context = assistant_overview_context(kind, project)
        context["assistant_error"] = "This assistant is unavailable."
        return render(request, "shared/_assistant_panel.html", context)

    scope_label = project.name if project is not None else "global"
    name = unique_session_name(f"{assistant_name} - {scope_label}")
    try:
        session_version = assistant.latest_agent_version.get_or_create_session(
            name=name,
            display_name=name,
            description="",
            workspace=workspace,
            group_key=f"assistant:{assistant_name}",
        )
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not create %s assistant chat", kind)
        context = assistant_overview_context(kind, project)
        context["assistant_error"] = "Could not create an assistant chat."
        return render(request, "shared/_assistant_panel.html", context)

    session = session_version.session
    if project is not None and session.parent_project_id != project.pk:
        session.parent_project = project
        session.save(update_fields=["parent_project_id"])
    context = assistant_overview_context(kind, project, str(session.pk))
    return render(request, "shared/_assistant_panel.html", context)


def _detail_path(kind: str) -> str:
    return {
        "agent": "agents",
        "skill": "skills",
        "cron": "cron",
        "project": "projects",
        "workspace": "workspaces",
    }[kind]
