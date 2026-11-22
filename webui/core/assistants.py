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
from webui.core.layout import unique_session_name

log = logging.getLogger(__name__)

_AGENTONE = "AgentOne"
_MEMORY_AGENT = "memory-manage"

# Every rightbar panel is either AgentOne or (on the Memory page) the memory
# specialist. Keep the model table separate from the assistant naming so a new
# panel kind does not repeat the same agent name five times.
_ENTITY_MODELS = {
    "agent": AgentModel,
    "skill": SkillModel,
    "cron": Cronjob,
    "project": Project,
    "workspace": WorkspaceModel,
}
_ASSISTANTS = {kind: (_AGENTONE, model) for kind, model in _ENTITY_MODELS.items()}

_OVERVIEW_KINDS = (
    "dashboard",
    "agents",
    "projects",
    "workspaces",
    "cronjobs",
    "workitems",
)
_OVERVIEW_ASSISTANTS = {kind: (_AGENTONE, _AGENTONE) for kind in _OVERVIEW_KINDS}
# The Memory page talks to the memory specialist itself, not AgentOne.
_OVERVIEW_ASSISTANTS["memory"] = (_MEMORY_AGENT, "Memory agent")

# Page briefs for the one-time context notice. `focus` is written as a direct
# instruction to the model; `admin_scope` is the admin_tool scope that owns
# this page's records (None for pages that use dedicated tools instead).
_OVERVIEW_PAGES = {
    "dashboard": {
        "label": "Main dashboard",
        "url": "/app/",
        "focus": "Give a whole-system overview by combining the relevant scopes; nothing is selected here.",
        "admin_scope": None,
    },
    "agents": {
        "label": "Agents dashboard",
        "url": "/app/agents",
        "focus": "Inspect the agent catalogue, versions, visibility and ownership. Manifest edits go through coding, not the DB.",
        "admin_scope": "agents",
    },
    "projects": {
        "label": "Projects dashboard",
        "url": "/app/projects",
        "focus": "Inspect registered projects and the resources they own.",
        "admin_scope": "projects",
    },
    "workspaces": {
        "label": "Workspaces dashboard",
        "url": "/app/workspaces",
        "focus": "Inspect registered workspaces and their path nesting.",
        "admin_scope": "workspaces",
    },
    "cronjobs": {
        "label": "Cron dashboard",
        "url": "/app/cron",
        "focus": "Inspect job schedules, agents and dispatch history across the visible scope.",
        "admin_scope": "cronjobs",
    },
    "workitems": {
        "label": "Work items dashboard",
        "url": "/app/workitems",
        "focus": "Inspect the durable work queue. Use the dedicated workitems tools rather than admin_tool mutations.",
        "admin_scope": "workitems",
    },
    "memory": {
        "label": "Memory page",
        "url": "/app/memory",
        "focus": "Use the memory tools to explain the memory tree and help maintain it. Ground answers in stored memories and say when information is missing.",
        "admin_scope": None,
    },
}
_ENTITY_PAGES = {
    "agent": {
        "label": "Agent detail",
        "path": "agents",
        "focus": "Inspect this agent's live state and manifest location. Edits require a manifest change plus system.reload, not a DB write.",
        "admin_scope": "agents",
    },
    "skill": {
        "label": "Skill detail",
        "path": "skills",
        "focus": "Inspect this skill's version, usage and assigned agents. Use skills.load when the full instructions are needed.",
        "admin_scope": "skills",
    },
    "cron": {
        "label": "Cron job detail",
        "path": "cron",
        "focus": "Inspect this job's schedule, agent and message before advising on changes.",
        "admin_scope": "cronjobs",
    },
    "project": {
        "label": "Project detail",
        "path": "projects",
        "focus": "Inspect this project and the resources it owns.",
        "admin_scope": "projects",
    },
    "workspace": {
        "label": "Workspace detail",
        "path": "workspaces",
        "focus": "Inspect this workspace and its path-nested children.",
        "admin_scope": "workspaces",
    },
}

_SESSION_HINT_MARKER = "[Assistant session context]"


def _assistant_scope(kind: str, item):
    """Resolve ``(assistant, project, workspace)`` for an entity detail page.

    The workspace used to be minted per entity type (source scopes for
    agents/skills, a separate cronjobs row, ...). All AgentOne chats now share
    one rule — the workspace itself when the page is a workspace, else the
    project's primary workspace, else AgentOne home.
    """
    from runtime.workspace.workspaces import Workspaces

    if kind not in _ENTITY_MODELS:
        raise KeyError(f"Unknown assistant kind: {kind}")
    project = item if kind == "project" else getattr(item, "parent_project", None)
    workspace = item if kind == "workspace" else None
    return _AGENTONE, project, Workspaces.assistant_workspace(
        project=project, workspace=workspace
    )


def _overview_scope(kind: str, project: Project | None):
    """Resolve the runtime workspace/project binding for an overview panel."""
    from runtime.workspace.workspaces import Workspaces

    if kind not in _OVERVIEW_ASSISTANTS:
        raise KeyError(f"Unknown assistant kind: {kind}")
    assistant_name = _OVERVIEW_ASSISTANTS[kind][0]
    # Collection panels stay in the caller's scope; the dashboard is global.
    # Memory is a scope, not an entity, so it follows the selected project too.
    if kind == "dashboard":
        project = None
    return assistant_name, project, Workspaces.assistant_workspace(project=project)


def _sessions_for_scope(
    assistant_name: str, project: Project | None, workspace
) -> list[SessionModel]:
    from server.models.enums.session_enums import SessionType

    # One-off forks (auto-title, reflection, compaction, delegates) inherit the
    # assistant's agent/workspace/project, so without this filter they show up
    # in the panel's history and can even be auto-selected as the "latest" chat.
    # Real assistant chats stay visible even when they are `subsession` children.
    return list(
        SessionModel.objects.filter(
            latest_session_version__agent__name=assistant_name,
            latest_session_version__workspace=workspace,
            parent_project=project,
        ).exclude(
            session_type__in=(
                SessionType.SUBTASK_DELEGATE,
                SessionType.SUBTASK_FORK,
                SessionType.SUBTASK_COMPACT,
                SessionType.SUBTASK_HOOK,
                SessionType.TEST,
            )
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
        "assistant_title": _AGENTONE,
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
        # The panel renders chat-thread/chat-composer components; inline them
        # for panel fragment responses so they don't fan out placeholder loads.
        # Their builders own the message query, so no thread context is built
        # here (that was the second source of truth for the chat rendering).
        context["component_inline"] = True
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
    """Build the panel context for a dashboard/collection assistant."""
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
    if kind == "memory":
        item_name = f"Memory · {project.name}" if project else "Memory · all scopes"
        noun = "memory agent"
    else:
        item_name = project.name if project else "All scopes"
        noun = kind
    context = {
        "assistant_kind": kind,
        "assistant_title": title,
        "assistant_noun": noun,
        "assistant_item": {"name": item_name},
        "assistant_sessions": sessions,
        "assistant_session": selected,
        "assistant_error": "",
        "assistant_panel_url": panel_url,
        "assistant_open_url": reverse("webui:assistant_overview_open", args=[kind]),
        "assistant_project_id": project.pk if project else "",
    }
    if selected is not None:
        # The panel renders chat-thread/chat-composer components; inline them
        # for panel fragment responses so they don't fan out placeholder loads.
        # Their builders own the message query, so no thread context is built
        # here (that was the second source of truth for the chat rendering).
        context["component_inline"] = True
    return context


# ---------------------------------------------------------------------------
# Session creation
# ---------------------------------------------------------------------------

def _open_assistant_chat(
    assistant_name: str,
    project: Project | None,
    workspace,
    name: str,
    group_key: str,
):
    """Get or create the scoped assistant chat and stamp its project."""
    assistant = AgentModel.objects.filter(name=assistant_name).first()
    if assistant is None or assistant.latest_agent_version is None:
        return None, None
    try:
        session_version = assistant.latest_agent_version.get_or_create_session(
            name=name,
            display_name=name,
            description="",
            workspace=workspace,
            group_key=group_key,
        )
        session = session_version.session
        if project is not None and session.parent_project_id != project.pk:
            session.parent_project = project
            session.save(update_fields=["parent_project_id"])
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not create %s assistant chat", assistant_name)
        return None, None
    return session, session_version


def _context_notice_text(
    *,
    assistant_name: str,
    page: dict,
    subject: str,
    subject_ref: str,
    project: Project | None,
    workspace,
) -> str:
    """Build the pinned operating brief for a new rightbar chat."""
    if workspace is not None:
        label = workspace.name or workspace.path or "unnamed"
        anchor = f'workspace "{label}" (id={workspace.pk})'
    else:
        anchor = "AgentOne home"
    anchor += (
        f', project "{project.name}" (id={project.pk})'
        if project is not None
        else ", global (no project selected)"
    )

    lines = [
        _SESSION_HINT_MARKER,
        f"You are the rightbar assistant on the {page['label']} ({page['url']}).",
    ]
    if subject_ref:
        lines.append(
            f"Record in focus: {subject} ({subject_ref}). Resolve unqualified references like 'this' or 'it' to this record unless the user says otherwise."
        )
    else:
        lines.append(
            "No single record is selected. This is a collection-level view; ask which record to act on when the request is ambiguous."
        )
    lines.extend([
        f"Your job here: {page['focus']}",
        f"Scope anchor: {anchor}. This anchor selects which chats appear here; it is not a permission boundary for admin_tool.",
        "",
        "Operating rules:",
    ])
    if assistant_name != _AGENTONE:
        lines.extend([
            "- Ground answers in the memory tree and say when information is missing.",
            "- Confirm before changing or deleting memories.",
        ])
    else:
        admin_scope = page.get("admin_scope")
        if admin_scope == "workitems":
            lines.append(
                "- Use the dedicated workitems tools for work-item actions; check their help before mutating."
            )
        elif admin_scope:
            lines.append(
                f'- For work on this page, call admin_tool(scope="{admin_scope}", action="help") first to discover the exact arguments for the action you need.'
            )
        else:
            lines.append(
                '- Call admin_tool(scope="help") to find the right scope, then admin_tool(scope=..., action="help") before using a specific action.'
            )
        lines.extend([
            "- Prefer read-only inspection. Ask before creating, updating, archiving or otherwise changing state.",
            "- If the target is outside the page in focus or this anchor, pass it explicitly with project_pk/project_name or workspace_pk/workspace_name. IDs are safest; names may be partial only if unambiguous.",
            "- Do not claim a change succeeded unless the tool returned success.",
        ])
    return "\n".join(lines)


def _ensure_session_context_notice(
    session_version,
    *,
    assistant_name: str,
    kind: str,
    page: dict,
    subject: str,
    subject_ref: str = "",
    project: Project | None,
    workspace,
):
    """Pin a one-time operating brief describing the page this chat came from.

    Most rightbar chats share the AgentOne home workspace, so a workspace row
    alone cannot tell the model which page it is serving or what "this job"
    refers to. This notice gives it that context plus concrete tool-use rules.
    """
    from runtime.session.session import Session as SessionRuntime
    from server.models.enums.message_enums import (
        MessageContentType,
        MessagePartType,
        MessageRole,
        MessageType,
    )
    from server.models.message import Message

    session_model = session_version.session
    if Message.objects.filter(
        session=session_model,
        message_type=MessageType.SYSTEM_NOTICE,
        parts__type=MessagePartType.MESSAGE,
        parts__content__content__contains=_SESSION_HINT_MARKER,
    ).exists():
        return None

    text = _context_notice_text(
        assistant_name=assistant_name,
        page=page,
        subject=subject,
        subject_ref=subject_ref,
        project=project,
        workspace=workspace,
    )

    try:
        last = SessionRuntime(
            session_model=session_model, pinned_session_version=session_version
        ).get_last_message()
        notice = Message.objects.create(
            session=session_model,
            session_version=session_version,
            role=MessageRole.USER,
            message_type=MessageType.SYSTEM_NOTICE,
            pin_to_context=True,
            prev_message=last,
        )
        notice.add_part(
            type=MessagePartType.MESSAGE,
            content_type=MessageContentType.TEXT,
            content=text,
        )
        notice.publish("create")
        return notice
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not write assistant context notice for %s", kind)
        return None


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
    _assistant_name, model = _ASSISTANTS[kind]
    item = get_object_or_404(model, pk=item_id)
    try:
        assistant_name, project, workspace = _assistant_scope(kind, item)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not resolve %s assistant scope for %s", kind, item_id)
        if request.headers.get("HX-Request") == "true":
            return render(request, "shared/_assistant_panel.html", {
                "assistant_kind": kind,
                "assistant_title": _AGENTONE,
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

    base_name = f"{kind.capitalize()} Assistant - {item.name}"
    name = unique_session_name(base_name)
    session, session_version = _open_assistant_chat(
        assistant_name, project, workspace, name,
        group_key=f"assistant:{kind}:{assistant_name}",
    )
    if session is None:
        if request.headers.get("HX-Request") == "true":
            context = assistant_panel_context(kind, item)
            context["assistant_error"] = "This assistant is unavailable."
            return render(request, "shared/_assistant_panel.html", context)
        return redirect(f"/app/{_detail_path(kind)}/{item.pk}?error=assistant-unavailable")

    page = dict(_ENTITY_PAGES[kind])
    page["url"] = f"/app/{page.pop('path')}/{item.pk}"
    _ensure_session_context_notice(
        session_version,
        assistant_name=assistant_name,
        kind=kind,
        page=page,
        subject=getattr(item, "name", str(item.pk)),
        subject_ref=f"{kind} id={item.pk}",
        project=project,
        workspace=workspace,
    )
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

    scope_label = project.name if project is not None else "global"
    name = unique_session_name(f"{assistant_name} - {scope_label}")
    session, session_version = _open_assistant_chat(
        assistant_name, project, workspace, name,
        group_key=f"assistant:{kind}:{assistant_name}",
    )
    if session is None:
        context = assistant_overview_context(kind, project)
        context["assistant_error"] = "This assistant is unavailable."
        return render(request, "shared/_assistant_panel.html", context)

    _ensure_session_context_notice(
        session_version,
        assistant_name=assistant_name,
        kind=kind,
        page=_OVERVIEW_PAGES[kind],
        subject=scope_label,
        project=project,
        workspace=workspace,
    )
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
