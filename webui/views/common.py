"""Shared context helpers for the server-rendered UI.

Every page is a normal Django view.  Links stay real ``<a href>`` anchors so
new tabs, bookmarks and no-JS work; ``hx-boost`` (set on ``<body>``) upgrades an
ordinary click to a partial swap that only replaces the page shell.  Fragments
are fetched by htmx on SSE events.
"""

from __future__ import annotations

import gzip
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import patch_vary_headers

from runtime.session.aimodel_picker import model_groups
from runtime.settings import UserSettings, get_send_key
from server.models.agents.agent import AgentModel
from server.models.enums.session_enums import SessionType
from server.models.message import Message
from server.models.sessions.session import SessionModel
from server.models.settings import ReasoningEffort
from server.models.workspace import WorkspaceModel
from webui.chat_cards import build_chat_cards
from webui.thread import DEFAULT_LIMIT, build_thread

log = logging.getLogger(__name__)

SIDEBAR_LIMIT = 80
#: Sidebar child-session tree (mirrors the legacy sidebar).
RECENT_SUBSESSION_WINDOW = timedelta(minutes=30)
MAX_INACTIVE_SUBSESSIONS = 5
SESSION_TREE_MAX_DEPTH = 8
_CHILD_SESSION_TYPES = (
    SessionType.SESSION,
    SessionType.CRONJOB,
    SessionType.SUBSESSION,
    SessionType.SUBTASK_COMPACT,
    SessionType.SUBTASK_DELEGATE,
)

#: Rail navigation.  ``section`` is the URL name suffix used by ``webui:urls``.
NAV_SECTIONS = (
    ("dashboard", "Dashboard"),
    ("chats", "Chats"),
    ("agents", "Agents"),
    ("projects", "Projects"),
    ("workspaces", "Spaces"),
    ("skills", "Skills"),
    ("cron", "Cron"),
    ("collections", "Data flows"),
    ("workitems", "Work items"),
    ("insights", "Insights"),
    ("logs", "Logs"),
    ("settings", "Settings"),
)

#: Which observable keys refresh each sidebar.  The stream carries event
#: *names*, so the trigger is just the model key.
SIDEBAR_TRIGGERS = {
    "dashboard": "sse:SessionModel delay:400ms",
    "chats": "sse:SessionModel delay:400ms",
    "agents": "sse:AgentModel delay:400ms",
    "projects": "sse:Project delay:400ms, sse:SessionModel delay:600ms",
    "workspaces": "sse:WorkspaceModel delay:400ms",
    "skills": "sse:SkillModel delay:400ms",
    "cron": "sse:Cronjob delay:400ms",
    "collections": "sse:DataCollection delay:400ms",
    "workitems": "sse:WorkItem delay:400ms",
}

SIDEBAR_TEMPLATES = {
    "dashboard": "webui/shell/panels/_chats.html",
    "chats": "webui/shell/panels/_chats.html",
    "agents": "webui/shell/panels/_agents.html",
    "projects": "webui/shell/panels/_projects.html",
    "workspaces": "webui/shell/panels/_workspaces.html",
    "skills": "webui/shell/panels/_skills.html",
    "cron": "webui/shell/panels/_cron.html",
    "collections": "webui/shell/panels/_collections.html",
    "workitems": "webui/shell/panels/_workitems.html",
    "insights": "webui/shell/panels/_insights.html",
    "logs": "webui/shell/panels/_logs.html",
    "settings": "webui/shell/panels/_settings.html",
}

#: Any-model keys used by the global SSE stream.
GLOBAL_SSE_KEYS = (
    "SessionModel",
    "AgentModel",
    "Project",
    "WorkspaceModel",
    "SkillModel",
    "Cronjob",
    "DataCollection",
    "WorkItem",
)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

def appearance() -> dict[str, str]:
    """Read the shared skin/theme preferences (best effort)."""
    try:
        settings_obj = UserSettings()
        return {
            "skin": settings_obj.skin or "slate",
            "theme": settings_obj.theme or "system",
            "font_size": settings_obj.font_size or "default",
        }
    except Exception:  # pylint: disable=broad-exception-caught
        return {"skin": "slate", "theme": "system", "font_size": "default"}


def send_key() -> str:
    try:
        return get_send_key()
    except Exception:  # pylint: disable=broad-exception-caught
        return "ctrl+enter"


def panel_open_default() -> bool:
    """Whether the session panel should start open (user preference)."""
    try:
        return bool(UserSettings().workspace_panel_open)
    except Exception:  # pylint: disable=broad-exception-caught
        return False


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def sidebar_sessions(limit: int = SIDEBAR_LIMIT) -> list[SessionModel]:
    """Top-level user conversations, pinned first (mirrors the legacy sidebar)."""
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
    """Children of *parents* to show: active plus recently active, capped."""
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
    """Attach ``children`` / ``tree_depth`` attributes for template nesting."""

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
    """Yield every session in the sidebar tree, parents before children."""
    for session in sessions:
        yield session
        yield from flatten_session_tree(getattr(session, "children", []) or [])


def thread_triggers(session_pk: int) -> str:
    """Build ``hx-trigger`` for the thread: one debounced SSE trigger per key."""
    keys = [
        f"Message.session:{session_pk}",
        f"Query.session:{session_pk}",
        f"Response.session:{session_pk}",
        f"AgentTaskCall.session:{session_pk}",
        f"SessionModel.pk:{session_pk}",
    ]
    return ", ".join(f"sse:{key} delay:150ms" for key in keys)


def is_busy(session_model: SessionModel) -> bool:
    try:
        return bool(session_model.get_runtime().is_busy())
    except Exception:  # pylint: disable=broad-exception-caught
        return False


def session_context(
    session_model: SessionModel,
    limit: int = DEFAULT_LIMIT,
    around: int | None = None,
) -> dict:
    limit = max(1, min(int(limit), 2000))
    rows = build_thread(session_model, limit=limit, end_pk=around)
    try:
        total_qs = Message.objects.filter(session=session_model)
        if around is not None:
            total_qs = total_qs.filter(pk__lte=around)
        total_messages = total_qs.count()
    except Exception:  # pylint: disable=broad-exception-caught
        total_messages = len(rows)
    return {
        "session": session_model,
        "rows": rows,
        "thread_limit": limit,
        "thread_around": around,
        "thread_has_older": total_messages > limit,
        "thread_older_limit": min(limit + DEFAULT_LIMIT, 2000),
        "cards": build_chat_cards(session_model),
        "thread_triggers": thread_triggers(session_model.pk),
        "toc_segments": compaction_segments(session_model),
        "sse_url": f"{reverse('webui:sse')}?scope=session:{session_model.pk}",
    }


_RING_CIRCUMFERENCE = 2 * 3.141592653589793 * 9.75


def _fmt_tokens(value) -> str:
    """Compact token count (matches the legacy context tooltip)."""
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return "0"
    if number >= 10_000_000:
        return f"{number / 1_000_000:.0f}M"
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if number >= 1_000:
        return f"{number / 1_000:.0f}k"
    return str(number)


def usage_summary(session_model: SessionModel) -> dict:
    """Context-window usage for the chat header ring and tooltip."""
    try:
        usage = session_model.get_runtime().context_usage()
    except Exception:  # pylint: disable=broad-exception-caught
        return {}
    percent = float(usage.get("used_context_percent", 0) or 0)
    fraction = max(0.0, min(1.0, percent / 100.0))
    used = usage.get("used_context_tokens", 0) or 0
    window = usage.get("max_context_tokens", 0) or 0
    return {
        "used": used,
        "window": window,
        "percent": percent,
        "percent_label": f"{percent:.0f}%",
        "ring_offset": f"{_RING_CIRCUMFERENCE * (1.0 - fraction):.2f}",
        "ring_circumference": f"{_RING_CIRCUMFERENCE:.2f}",
        "used_label": _fmt_tokens(used),
        "window_label": _fmt_tokens(window) if window else "",
        "tokens_send": _fmt_tokens(usage.get("tokens_send", 0)),
        "tokens_received": _fmt_tokens(usage.get("tokens_received", 0)),
        "tokens_cached": _fmt_tokens(usage.get("tokens_cached", 0)),
        "tokens_reasoning": _fmt_tokens(usage.get("tokens_reasoning", 0)),
        "cache_hit_rate": usage.get("cache_hit_rate", 0) or 0,
        "reasoning_percent": usage.get("tokens_reasoning_percent", 0) or 0,
        "level": "high" if percent >= 85 else ("mid" if percent >= 60 else ""),
    }


def command_options(session_model: SessionModel) -> list[dict]:
    """Slash commands and tools the agent may invoke, with their schema fields.

    Mirrors the legacy ``CommandDropdown``: it merges ``allowedCommands`` and
    ``allowedTools`` and derives a small form from each task's JSON schema.
    """
    try:
        runtime = session_model.get_runtime()
    except Exception:  # pylint: disable=broad-exception-caught
        return []
    try:
        command_names = set(runtime.allowedCommandNames or [])
        tool_names = set(runtime.allowedToolNames or [])
        allowed_commands = list(runtime.allowedCommands or [])
        allowed_tools = list(runtime.allowedTools or [])
        versions = allowed_commands + allowed_tools
    except Exception:  # pylint: disable=broad-exception-caught
        return []

    options: list[dict] = []
    seen: set[str] = set()
    for version in versions:
        definition = getattr(version, "task_definition", None)
        name = getattr(definition, "name", "")
        if not name or name in seen:
            continue
        if name not in command_names and name not in tool_names:
            continue
        seen.add(name)
        options.append(
            {
                "name": name,
                "description": getattr(definition, "description", "") or "",
                "fields": _schema_fields(getattr(version, "function_schema", None)),
            }
        )
    options.sort(key=lambda item: item["name"])
    return options


def _schema_fields(schema) -> list[dict]:
    if not isinstance(schema, dict):
        return []
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    fields: list[dict] = []
    for name, prop in properties.items():
        if not isinstance(prop, dict):
            prop = {}
        prop_type = prop.get("type", "string")
        fields.append(
            {
                "name": name,
                "type": prop_type,
                "input_type": "number" if prop_type in ("integer", "number") else "text",
                "required": name in required,
                "placeholder": prop.get("description", "") or "",
                "description": prop.get("description", "") or "",
                "enum": prop.get("enum") or [],
            }
        )
    return fields


def compaction_segments(session_model: SessionModel) -> list[dict]:
    """Compaction boundaries for the chat table-of-contents rail."""
    from server.models.enums.message_enums import MessageType

    try:
        pks = list(
            Message.objects.filter(
                session=session_model,
                message_type=MessageType.COMPACTION,
            )
            .order_by("pk")
            .values_list("pk", flat=True)
        )
    except Exception:  # pylint: disable=broad-exception-caught
        return []
    return [
        {"pk": pk, "label": f"Section {index + 1}", "index": index}
        for index, pk in enumerate(pks)
    ]


def composer_config(session_model: SessionModel) -> dict:
    """Model / reasoning / workspace pickers for the chat composer.

    Kept out of :func:`session_context` because the thread fragment is
    refetched on every SSE event and does not render the composer.
    """
    context: dict = {
        "composer_model": "",
        "composer_models": [],
        "composer_agent_id": None,
        "composer_agents": [],
        "composer_reasoning": ReasoningEffort.NONE,
        "composer_reasoning_choices": ReasoningEffort.choices,
        "composer_workspace_id": None,
        "composer_workspaces": [],
    }
    try:
        runtime = session_model.get_runtime()
    except Exception:  # pylint: disable=broad-exception-caught
        return context
    try:
        current = runtime.aimodel
        context["composer_model"] = current.name if current is not None else ""
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        context["composer_agent_id"] = runtime.agent.model.pk
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        context["composer_agents"] = list(
            AgentModel.objects.filter(is_archived=False, parent_agent__isnull=True)
            .order_by("name")
        )
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        context["composer_models"] = [group.name for group in model_groups()]
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        context["composer_reasoning"] = runtime.reasoning_effort or ReasoningEffort.NONE
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        workspace = runtime.workspace
        context["composer_workspace_id"] = workspace.pk if workspace is not None else None
        context["composer_workspaces"] = list(
            WorkspaceModel.objects.order_by("name").only("pk", "name", "path")
        )
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return context


def composer_state(session_model: SessionModel) -> dict:
    """Busy/paused state and the primary send action for the composer.

    Mirrors the legacy composer footer: when the session is busy the send
    button becomes queue/interrupt/steer according to the scheduler
    strategy, and stop/pause buttons appear.
    """
    state = {
        "composer_busy": False,
        "composer_paused": bool(getattr(session_model, "is_paused", False)),
        "composer_mode": "send",
        "composer_queued": 0,
    }
    try:
        runtime = session_model.get_runtime()
    except Exception:  # pylint: disable=broad-exception-caught
        return state
    try:
        state["composer_busy"] = bool(runtime.is_busy())
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    # Keep the model-field value (already loaded) to avoid a per-page DB read.
    if state["composer_busy"]:
        try:
            strategy = runtime.scheduler_strategy
        except Exception:  # pylint: disable=broad-exception-caught
            strategy = None
        if strategy == "interrupt":
            state["composer_mode"] = "interrupt"
        elif strategy == "merge":
            state["composer_mode"] = "steer"
        elif strategy == "parallel":
            state["composer_mode"] = "send"
        else:
            state["composer_mode"] = "queue"
    try:
        from server.models.enums.task_enums import TaskCallStatusDetail

        state["composer_queued"] = session_model.related_agent_task_calls.filter(
            status_detail=TaskCallStatusDetail.WAITING_QUEUE
        ).count()
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return state


def default_agent() -> AgentModel | None:
    qs = AgentModel.objects.filter(
        is_archived=False,
        parent_agent__isnull=True,
        parent_skill__isnull=True,
        latest_agent_version__isnull=False,
    )
    for name in ("AgentOne", "baseagent", "general-chat", "coding"):
        agent = qs.filter(name=name).first()
        if agent is not None and agent.is_user_visible:
            return agent
    for agent in qs[:25]:
        if agent.is_user_visible:
            return agent
    return None


def unique_session_name(base: str) -> str:
    name = base
    if SessionModel.objects.filter(name=name).exists():
        stamp = datetime.now().strftime("%Y.%m.%d-%H:%M:%S")
        name = f"{base} {stamp}"
        index = 2
        while SessionModel.objects.filter(name=name).exists():
            name = f"{base} {stamp}-{index}"
            index += 1
    return name


# ---------------------------------------------------------------------------
# Shell context
# ---------------------------------------------------------------------------

def _sidebar_query(request, section: str, active_id) -> str:
    params = {}
    for key in ("project", "q", "archived"):
        value = request.GET.get(key)
        if value not in (None, ""):
            params[key] = value
    params["section"] = section
    if active_id not in (None, ""):
        params["active"] = str(active_id)
    return urlencode(params)


def _sidebar_project_id(request):
    """Resolve the sidebar's project filter, persisting it in the session.

    ``?project=<pk>`` sets the filter (empty value clears it). Pages without
    the parameter inherit the last choice, matching the legacy sidebar's
    ``ProjectSelector`` which kept its selection while switching tabs.
    """
    if "project" in request.GET:
        raw = request.GET.get("project") or ""
        project_id = int(raw) if raw.isdigit() else None
        if request.session.get("sidebar_project_id") != project_id:
            request.session["sidebar_project_id"] = project_id
    else:
        project_id = request.session.get("sidebar_project_id")

    from server.models.project import Project

    if project_id is not None and not Project.objects.filter(pk=project_id).exists():
        project_id = None
        request.session["sidebar_project_id"] = None
    return project_id


def shell_context(request, section: str, active_id=None) -> dict:
    """Common context for every full page: rail, sidebar and preferences."""
    context = {
        "sections": NAV_SECTIONS,
        "section": section,
        "active_id": active_id,
        "sidebar_template": SIDEBAR_TEMPLATES.get(section, SIDEBAR_TEMPLATES["chats"]),
        "sidebar_triggers": SIDEBAR_TRIGGERS.get(section, ""),
        "sidebar_qs": _sidebar_query(request, section, active_id),
        "global_sse_url": f"{reverse('webui:sse')}?scope=global",
    }
    context.update(sidebar_context(request, section, active_id))
    context.update(appearance())
    return context


def is_htmx_request(request) -> bool:
    """True for htmx requests (boosts and explicit fragment fetches)."""
    return request.headers.get("HX-Request") == "true"


def is_boosted_request(request) -> bool:
    """True when htmx intercepted a normal link/form (``hx-boost``)."""
    return request.headers.get("HX-Boosted") == "true"


def render_page(request, section: str, template: str, context: dict | None = None,
                active_id=None) -> object:
    """Render a page, or just the swappable shell for boosted navigation.

    Full document loads (new tabs, reloads, no-JS) get the complete
    ``base.html`` layout.  htmx navigation gets ``hx_base.html``: a ``<title>``
    followed by exactly the markup that lives inside ``<body>``, so the page
    keeps its single SSE connection, rail and sidebar without a document
    reload.  Both variants render the same block structure, so no view needs
    to know which one the client asked for.
    """
    ctx = shell_context(request, section, active_id)
    ctx["layout_base"] = (
        "webui/hx_base.html" if is_htmx_request(request) else "webui/base.html"
    )
    # Live pages must not come back from the htmx history snapshot: a restored
    # chat would show the messages that existed when it was cached.  With
    # ``hx-history="false"`` a back/forward triggers the normal cache-miss
    # refetch, which lands here and renders fresh state.
    ctx["disable_history"] = template.startswith("webui/chat/")
    ctx.update(context or {})
    response = render(request, template, ctx)
    patch_vary_headers(response, ("HX-Request",))
    # Authenticated HTML must never be reused without revalidation: a cached
    # fragment served for a real navigation (or the reverse) would break the
    # shell.  ``Vary`` keeps the two variants apart, ``no-cache`` keeps both
    # fresh while still allowing bfcache/history restores.
    response["Cache-Control"] = "private, no-cache"
    _gzip_html(request, response)
    return response


def _gzip_html(request, response, *, minimum: int = 1024) -> None:
    """Compress a rendered page in place.

    A chat page is easily hundreds of kilobytes of markup, so this is the
    single cheapest way to make navigation feel fast on a remote connection.
    Only page responses go through here: SSE streams and API responses keep
    their identity encoding, where a compressor would add buffering.
    """
    body = response.content
    if len(body) < minimum:
        return
    if "gzip" not in request.headers.get("Accept-Encoding", "").lower():
        return
    patch_vary_headers(response, ("Accept-Encoding",))
    response.content = gzip.compress(body, compresslevel=6)
    response["Content-Encoding"] = "gzip"
    response["Content-Length"] = str(len(response.content))


def _session_activity(sessions: list[SessionModel]) -> dict:
    """Flag sessions that are streaming or waiting for user approval.

    Mirrors the legacy sidebar's ``mark_active`` / ``mark_needs_approval``
    indicators, batched into two queries for the whole sidebar.
    """
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


def sidebar_context(request, section: str, active_id=None) -> dict:
    """Data needed by the domain sidebar panel."""
    from server.models.project import Project

    project_id = _sidebar_project_id(request)
    ctx: dict = {
        "section": section,
        "active_id": active_id,
        "sidebar_query": _sidebar_query(request, section, active_id),
        "sidebar_project_id": project_id,
        "sidebar_projects": list(Project.objects.order_by("name")),
    }

    if section in ("dashboard", "chats"):
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
        attach_session_children(sessions, include_archived=show_archived)
        ctx["sidebar_sessions"] = sessions
        ctx["show_archived"] = show_archived
        ctx["q"] = query
        ctx["subagent_count"] = SessionModel.objects.filter(
            parent_session__isnull=False,
            is_active=True,
            session_type=SessionType.SESSION,
        ).count()
        ctx.update(_session_activity(list(flatten_session_tree(sessions))))
        ctx["projects"] = ctx["sidebar_projects"]

    elif section == "agents":
        qs = AgentModel.objects.filter(is_archived=False)
        if project_id is not None:
            qs = qs.filter(parent_project_id=project_id)
        ctx["sidebar_agents"] = list(
            qs.select_related("latest_agent_version", "parent_project").order_by("name")
        )

    elif section == "projects":
        pass

    elif section == "workspaces":
        from server.models.workspace import WorkspaceModel
        from ui.sidebar.panels.workspaces import build_workspace_tree

        items = list(
            WorkspaceModel.objects.select_related("parent_project").order_by("name")
        )
        ctx["sidebar_workspaces"] = build_workspace_tree(items)

    elif section == "skills":
        from server.models.skills.skill import SkillModel

        show_archived = request.GET.get("archived") == "1"
        qs = SkillModel.objects.filter(is_archived=show_archived)
        if project_id is not None:
            qs = qs.filter(parent_project_id=project_id)
        ctx["sidebar_skills"] = list(
            qs.select_related(
                "parent_agent", "parent_project", "parent_skill", "latest_skill_version"
            ).order_by("name")
        )
        ctx["show_archived"] = show_archived

    elif section == "cron":
        from server.models.cron import Cronjob

        qs = Cronjob.objects.filter(is_archived=False)
        if project_id is not None:
            qs = qs.filter(parent_project_id=project_id)
        ctx["sidebar_cronjobs"] = list(
            qs.select_related("agent", "parent_project").order_by("-is_active", "name")
        )

    elif section == "collections":
        from server.models.collections.data_collection import DataCollection

        ctx["sidebar_collections"] = list(
            DataCollection.objects.select_related("parent_project").order_by("name")
        )


    elif section == "workitems":
        from server.models.project import Project
        from server.models.workitems.enums import WorkItemStatus
        from server.models.workitems.work_item import WorkItem

        raw_project = request.GET.get("project", "")
        project_id = (
            int(raw_project)
            if raw_project.isdigit()
            else ctx["sidebar_project_id"]
        )
        qs = WorkItem.objects.select_related("assigned_agent").order_by("-priority", "created_at")
        if project_id is not None:
            qs = qs.filter(project_id=project_id)
        items = list(qs[:400])
        counts = {value: 0 for value, _ in WorkItemStatus.choices}
        for item in items:
            counts[item.status] = counts.get(item.status, 0) + 1
        ctx.update(
            {
                "sidebar_workitems": items,
                "sidebar_workitem_counts": counts,
                "sidebar_workitem_columns": [
                    {
                        "value": value,
                        "label": label,
                        "count": counts.get(value, 0),
                    }
                    for value, label in WorkItemStatus.choices
                ],
                "projects": list(Project.objects.order_by("name")),
                "selected_project": project_id,
                "terminal_count": counts.get(WorkItemStatus.DONE, 0)
                + counts.get(WorkItemStatus.CANCELLED, 0),
            }
        )

    elif section == "logs":
        from django.conf import settings as django_settings

        ctx["log_files"] = _log_files()
        ctx["log_dir"] = str(django_settings.LOG_DIR or "")
        ctx["selected_log"] = request.GET.get("file") or (ctx["log_files"][0] if ctx["log_files"] else "")

    elif section == "settings":
        ctx["settings_tabs"] = _settings_tabs()

    elif section == "insights":
        ctx["insight_tabs"] = _insight_tabs()

    return ctx


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def _log_files() -> list[str]:
    from django.conf import settings

    if not settings.LOG_DIR:
        return []
    try:
        from pathlib import Path

        return sorted(p.name for p in Path(settings.LOG_DIR).glob("*.log"))
    except OSError:
        return []


def _settings_tabs() -> list[tuple[str, str]]:
    return [
        ("appearance", "Appearance"),
        ("preferences", "Preferences"),
        ("providers", "Providers"),
        ("system", "System"),
    ]


def _insight_tabs() -> list[tuple[str, str]]:
    return [
        ("dashboard", "Dashboard"),
        ("analytics", "Analytics"),
        ("providers", "Providers"),
        ("models", "Models"),
    ]
