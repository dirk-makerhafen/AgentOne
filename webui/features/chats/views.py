"""Chat page, fragments and actions."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from urllib.parse import urlencode

from django.core.cache import cache
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from server.models.enums.session_enums import SessionType
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail, TaskSchedulerStrategy
from server.models.agents.agent import AgentModel
from server.models.content import GenericContent, resolve_generic_content_refs
from server.models.enums.message_enums import MessageType
from server.models.message import Message, MessagePart
from server.models.queries.query import Query, QueryStatus
from server.models.queries.response import Response
from server.models.sessions.session import SessionModel
from server.models.settings import ReasoningEffort
from server.models.settings import AgentToolCallSyntax, ResponseTemperature, SubagentResultDelivery
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.workspace import WorkspaceModel
from webui.features.workspaces.views import directory_url, workspace_tree_context
from webui.features.chats.parts.cards import queue_text
from webui.features.chats.parts.thread import (
    DEFAULT_LIMIT,
    build_call_detail,
    build_query_detail,
    build_thread,
)
from webui.core.layout import default_agent, panel_open_default, render_page, send_key, unique_session_name
from webui.features.chats.session_ui import (
    command_options,
    compaction_segments,
    composer_config,
    composer_state,
    is_busy,
    session_context,
    usage_summary,
)

log = logging.getLogger(__name__)

PANEL_TABS = (
    ("details", "Details"),
    ("workspace", "Workspace"),
    ("settings", "Settings"),
    ("capabilities", "Capabilities"),
    ("tasks", "Tasks"),
    ("calls", "Calls"),
    ("subagents", "Subagents"),
    ("templates", "Templates"),
    ("todos", "Todos"),
    ("terminals", "Terminals"),
    ("history", "History"),
)

#: Cache keys for the templates tab.  The panel is stateless between htmx
#: fetches, so the preview text and the last dispatched run live in the cache.
_TEMPLATE_PREVIEW_TTL = 600
_TEMPLATE_RUN_TTL = 3600

#: Colored badges for the Calls tab (mirrors the legacy right panel).
_CALL_STATUS_COLORS = {
    TaskCallStatusDetail.NEW: "var(--muted)",
    TaskCallStatusDetail.WAITING_QUEUE: "var(--link)",
    TaskCallStatusDetail.WAITING_RETRY: "var(--warning)",
    TaskCallStatusDetail.WAITING_DEPENDENCY: "var(--link)",
    TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS: "var(--link)",
    TaskCallStatusDetail.WAITING_RATELIMIT: "var(--warning)",
    TaskCallStatusDetail.ACTIVE_QUEUED: "var(--accent)",
    TaskCallStatusDetail.ACTIVE_RUNNING: "var(--accent)",
    TaskCallStatusDetail.HALTED_INPUT: "var(--warning)",
    TaskCallStatusDetail.HALTED_APPROVAL: "#f59e0b",
    TaskCallStatusDetail.HALTED_STAGNATED: "var(--danger)",
    TaskCallStatusDetail.HALTED_PAUSED: "var(--muted)",
    TaskCallStatusDetail.ENDED_SUCCESS: "var(--success)",
    TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION: "var(--danger)",
    TaskCallStatusDetail.ENDED_FAILURE_LOGIC: "var(--danger)",
    TaskCallStatusDetail.ENDED_CANCELLED: "var(--muted)",
    TaskCallStatusDetail.ENDED_STOPPED: "var(--muted)",
}


def _template_preview_key(session_pk: int) -> str:
    return f"webui:template:preview:{session_pk}"


def _template_run_key(session_pk: int) -> str:
    return f"webui:template:run:{session_pk}"


def _template_error_key(session_pk: int) -> str:
    return f"webui:template:error:{session_pk}"


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def chat_page(request, session_id: int):
    session_model = get_object_or_404(
        SessionModel.objects.select_related(
            "latest_session_version__agent",
            "latest_session_version__agent__latest_agent_version",
            "latest_session_version__agent__latest_agent_version__agent_settings",
            "latest_session_version__pinned_agent_version",
            "latest_session_version__session_settings",
            "latest_session_version__workspace",
            "parent_project",
        ),
        pk=session_id,
    )
    context = session_context(session_model, around=_int_param(request.GET.get("around")))
    context["is_busy"] = is_busy(session_model)
    context["send_key"] = send_key()
    context["usage"] = usage_summary(session_model)
    context["commands"] = command_options(session_model)
    context.update(composer_config(session_model))
    context.update(composer_state(session_model))
    panel_tab = request.GET.get("panel", "")
    if not panel_tab and panel_open_default():
        panel_tab = "details"
    panel_context = _panel_context(session_model, panel_tab or "details", request)
    panel_context["panel_tab"] = panel_tab
    context.update(panel_context)
    return render_page(request, "chats", "chats/detail.html", context,
                       active_id=session_model.pk)


# ---------------------------------------------------------------------------
# Fragments
# ---------------------------------------------------------------------------

def thread_fragment(request, session_id: int):
    session_model = get_object_or_404(SessionModel, pk=session_id)
    raw_limit = request.GET.get("limit", "")
    limit = int(raw_limit) if raw_limit.isdigit() else DEFAULT_LIMIT
    around = _int_param(request.GET.get("around"))
    context = session_context(session_model, limit=limit, around=around)
    if request.GET.get("full") == "1":
        return render(request, "chats/parts/thread.html", context)
    return render(request, "chats/parts/thread_inner.html", context)


def query_detail(request, query_id: int):
    """Lazily render a query card's prompt messages on first expand."""
    query = get_object_or_404(Query, pk=query_id)
    error_type = ""
    error_message = ""
    try:
        response = query.related_response.order_by("-pk").first()
        if response is not None:
            error_type = response.error_type or ""
            error_message = response.error_message or ""
    except Exception:  # pylint: disable=broad-exception-caught
        response = None
    return render(
        request,
        "chats/parts/query_detail.html",
        {
            "query": query,
            "messages": build_query_detail(query),
            "error_type": error_type,
            "error_message": error_message,
        },
    )


def call_detail(request, call_id: int):
    """Lazily render an expanded tool card (arguments, result, sub-calls)."""
    call = get_object_or_404(
        AgentTaskCall.objects.select_related(
            "task_definition", "task_definition_version__task_definition"
        ),
        pk=call_id,
    )
    context = build_call_detail(call, full=request.GET.get("full") == "1")
    session_id = request.GET.get("session", "")
    if request.GET.get("back") == "1" and session_id.isdigit():
        context["back_session"] = int(session_id)
    return render(request, "chats/parts/tool_detail.html", context)


def inspect_history_item(request, session_id: int):
    """Return the full content of a history item (message or tool call)."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    message_pk = request.GET.get("message_pk")
    task_call_pk = request.GET.get("task_call_pk")
    max_chars = int(request.GET.get("max_chars", "8000"))

    try:
        runtime = session_model.get_runtime()
        tool = runtime.get_tool("inspect_history_item")
        if tool is None:
            return HttpResponse("History inspect tool not available.", status=503)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not get inspect_history_item tool for session %s", session_model.pk)
        return HttpResponse("Could not initialize history inspect.", status=503)

    if (message_pk is None) == (task_call_pk is None):
        return HttpResponse("Pass exactly one of message_pk or task_call_pk.", status=400)

    result = tool.call(
        message_pk=int(message_pk) if message_pk else None,
        task_call_pk=int(task_call_pk) if task_call_pk else None,
        max_chars=max_chars,
    )

    if "error" in result:
        return HttpResponse(f"Error: {result['error']}", status=404)

    if result.get("type") == "message":
        context = {
            "message": result,
            "session": session_model,
        }
        return render(request, "chats/parts/history_message_detail.html", context)
    else:
        # For tool calls, reuse the existing call_detail template
        call = get_object_or_404(
            AgentTaskCall.objects.select_related(
                "task_definition", "task_definition_version__task_definition"
            ),
            pk=result.get("task_call_pk"),
        )
        context = build_call_detail(call, full=True)
        context["back_session"] = session_id
        return render(request, "chats/parts/tool_detail.html", context)


def response_detail(request, response_id: int):
    """Lazily render a response card's body (for streaming tokens)."""
    response = get_object_or_404(Response, pk=response_id)
    return render(
        request,
        "chats/parts/response_detail.html",
        {"response": response},
    )


def chat_toc(request, session_id: int):
    """Compaction-boundary rail; refreshed when a compaction message appears."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    return render(
        request,
        "chats/parts/toc.html",
        {
            "session": session_model,
            "toc_segments": compaction_segments(session_model),
        },
    )


def terminal_output(request, session_id: int, name: str):
    """Live tmux buffer for one named terminal (polled by the panel tab)."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    row = session_model.terminals.filter(name=name).first()
    if row is None:
        return HttpResponse("")
    output = ""
    error = ""
    try:
        from runtime.terminal import poll_output

        result = poll_output(session_model, name=row.name, lines=400)
        output = result.get("output", "") or ""
    except Exception as exc:  # pylint: disable=broad-exception-caught
        error = str(exc)
    return render(
        request,
        "chats/parts/terminal_output.html",
        {"terminal": row, "output": output, "error": error},
    )


@require_POST
def terminal_kill(request, session_id: int, name: str):
    """Kill one named terminal and re-render the terminals tab."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    try:
        from runtime.terminal import kill_terminal

        kill_terminal(session_model, name=name)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not kill terminal %s for session %s", name, session_id)
        for _ts in session_model.terminals.filter(name=name):
            _ts.atomic_update(status="dead")
    return render(
        request,
        "chats/panels/inner.html",
        _panel_context(session_model, "terminals", request),
    )


def _header_context(session_model: SessionModel) -> dict:
    return {
        "session": session_model,
        "is_busy": is_busy(session_model),
        "usage": usage_summary(session_model),
    }


def chat_header(request, session_id: int):
    session_model = get_object_or_404(
        SessionModel.objects.select_related(
            "latest_session_version__agent", "parent_project"
        ),
        pk=session_id,
    )
    return render(request, "chats/parts/header.html", _header_context(session_model))


def _composer_footer_response(request, session_model: SessionModel):
    context = {
        "session": session_model,
        "send_key": send_key(),
    }
    context.update(composer_state(session_model))
    return render(request, "chats/parts/composer_footer.html", context)


def chat_composer_footer(request, session_id: int):
    """Busy/paused state for the composer buttons (refreshed by SSE)."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    return _composer_footer_response(request, session_model)


@require_POST
def composer_action(request, session_id: int):
    """Stop / pause / resume from the composer without reloading the page."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    action = request.POST.get("action", "")
    try:
        runtime = session_model.get_runtime()
        if action == "stop":
            runtime.stop_generation()
        elif action == "pause":
            runtime.pause()
        elif action == "resume":
            runtime.resume()
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("composer action %s failed for session %s", action, session_id)
    return _composer_footer_response(request, session_model)


def chat_panel(request, session_id: int):
    """Right-hand session panel shell (tab strip + body)."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    tab = request.GET.get("tab") or "details"
    return render(
        request,
        "chats/rightbar.html",
        _panel_context(session_model, tab, request),
    )


def chat_panel_tab(request, session_id: int, tab: str):
    session_model = get_object_or_404(SessionModel, pk=session_id)
    return render(
        request,
        "chats/panels/inner.html",
        _panel_context(session_model, tab, request),
    )


def chat_panel_body(request, session_id: int, tab: str):
    """The panel body wrapper for one tab, including its SSE refetch URL.

    Tab clicks swap this element with ``hx-swap="outerHTML"`` so the new body
    carries the ``hx-get`` for the visible tab. htmx caches an element's request
    URL when it processes the node, so patching ``hx-get`` in place (what the
    old JS did) left SSE refreshes pointed at the tab rendered on page load.
    """
    session_model = get_object_or_404(SessionModel, pk=session_id)
    return render(
        request,
        "chats/rightbar_body.html",
        _panel_context(session_model, tab, request),
    )


def _panel_context(session_model: SessionModel, tab: str, request=None) -> dict:
    allowed = (
        "details", "workspace", "settings", "capabilities", "tasks", "calls",
        "subagents", "templates", "terminals", "todos", "history",
    )
    if tab not in allowed:
        tab = "details"
    context = {
        "session": session_model,
        "panel_tab": tab,
        "panel_tabs": PANEL_TABS,
    }
    try:
        runtime = session_model.get_runtime()
        context["usage"] = runtime.context_usage()
        context["has_agent_update"] = runtime.has_agent_update()
        pinned = runtime.pinned_agent_version
        latest = runtime.latest_agent_version
        context["pinned_agent_version"] = pinned.version_number if pinned else "?"
        context["latest_agent_version"] = latest.version_number if latest else "?"
    except Exception:  # pylint: disable=broad-exception-caught
        context["usage"] = {}
        context["has_agent_update"] = False

    if tab == "workspace":
        context.update(_workspace_context(session_model, request))
    elif tab == "settings":
        setting_rows = _session_setting_rows(session_model)
        context["setting_rows"] = setting_rows
        context["setting_sections"] = _setting_sections(setting_rows)
        context.update(_settings_header(session_model))
        context.update(composer_config(session_model))
    elif tab == "capabilities":
        context["capability_sections"] = _capability_sections(session_model)
    elif tab in ("tasks", "calls"):
        context["task_calls"] = list(
            session_model.related_agent_task_calls.select_related(
                "task_definition", "task_definition_version"
            ).order_by("-pk")[:60]
        )
        if tab == "calls":
            context.update(_current_call_tree(session_model))
    elif tab == "subagents":
        context["children"] = _child_session_rows(session_model)
        context["available_subagents"] = _available_subagents(session_model)
    elif tab == "terminals":
        context["terminals"] = _terminal_rows(session_model)
    elif tab == "todos":
        context["todos"] = _read_todos(session_model)
        try:
            context["todo_auto"] = bool(
                session_model.get_runtime()._get_session_setting("todo_auto_process")
            )
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("could not read todo auto state for session %s", session_model.pk)
            context["todo_auto"] = False
    elif tab == "templates":
        context["templates"] = _template_rows(session_model)
        context["template_preview"] = cache.get(_template_preview_key(session_model.pk))
        context["template_run"] = _template_run_state(session_model)
        context["template_error"] = cache.get(_template_error_key(session_model.pk)) or ""
    elif tab == "history":
        context["history_results"] = _search_history(session_model, request)
    return context


def _settings_header(session_model: SessionModel) -> dict:
    """Identity/summary fields for the Settings tab (name, type, bindings)."""
    version = session_model.latest_session_version
    agent = version.agent if version else None
    workspace = version.workspace if version else None
    model_name = ""
    version_number = ""
    version_is_latest = True
    try:
        runtime = session_model.get_runtime()
        aimodel = runtime.aimodel
        if aimodel is not None:
            model_name = aimodel.name
        version_number = runtime.get_version_model().version_number
        version_is_latest = runtime.is_newest_version()
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not load settings header for session %s", session_model.pk)
    if not model_name and version is not None:
        settings_model = getattr(version, "session_settings", None)
        if settings_model is not None and settings_model.aimodel is not None:
            model_name = settings_model.aimodel.name
    turn_count = ""
    unattended_turns = ""
    system_prompt = ""
    try:
        runtime = session_model.get_runtime()
        turn_count = runtime.current_turn_count
        unattended_turns = runtime.current_unattended_turn_count
        system_prompt = runtime.system_prompt or ""
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not load prompt details for session %s", session_model.pk)
    return {
        "settings_name": session_model.name,
        "settings_active": session_model.is_active,
        "settings_is_paused": session_model.is_paused,
        "settings_type_label": dict(SessionType.choices).get(
            session_model.session_type, str(session_model.session_type)
        ),
        "settings_agent": agent,
        "settings_workspace": workspace,
        "settings_model_name": model_name,
        "settings_version_number": version_number,
        "settings_version_is_latest": version_is_latest,
        "settings_turn_count": turn_count,
        "settings_unattended_turns": unattended_turns,
        "settings_system_prompt": system_prompt,
    }


def _child_session_rows(session_model: SessionModel) -> list[dict]:
    """Active child sessions with the status metadata the legacy tab showed."""
    children = list(
        SessionModel.objects.filter(
            parent_session=session_model,
            is_active=True,
        )
        .select_related(
            "latest_session_version__agent",
            "latest_session_version__session_settings__aimodel",
        )
        .order_by("-last_active_at")[:60]
    )
    rows = []
    for child in children:
        version = child.latest_session_version
        settings_model = getattr(version, "session_settings", None) if version else None
        model_name = (
            settings_model.aimodel.name
            if settings_model is not None and settings_model.aimodel is not None
            else ""
        )
        try:
            active = (
                Query.objects.filter(
                    session_version__session=child, status=QueryStatus.ACTIVE
                ).exists()
                or AgentTaskCall.objects.filter(session=child)
                .exclude(status=TaskCallStatus.ENDED)
                .exists()
            )
            needs_approval = AgentTaskCall.objects.filter(
                session=child,
                requires_approval=True,
                status_detail=TaskCallStatusDetail.HALTED_APPROVAL,
            ).exists()
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("could not resolve child session state for %s", child.pk)
            active = False
            needs_approval = False
        rows.append({
            "session": child,
            "model_name": model_name,
            "message_count": child.messages.count(),
            "active": active,
            "needs_approval": needs_approval,
        })
    return rows


def _terminal_rows(session_model: SessionModel) -> list[dict]:
    """Terminals with tmux liveness, newest first (DB fallback when tmux is down)."""
    try:
        from runtime.terminal import list_terminals

        rows = list_terminals(session_model)
        return sorted(rows, key=lambda row: row.get("name", ""))
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not read live terminals for session %s", session_model.pk)
        return [
            {
                "name": row.name,
                "status": row.status,
                "tmux": row.tmux_session_name,
                "alive": False,
                "cwd": row.cwd,
                "last_active_at": str(row.last_active_at) if row.last_active_at else None,
            }
            for row in session_model.terminals.order_by("name")
        ]


_SESSION_SETTING_FIELDS = (
    ("precision", "Precision"),
    ("reasoning_effort", "Reasoning effort"),
    ("scheduler_strategy", "Scheduler strategy"),
    ("tool_call_syntax", "Tool call syntax"),
    ("subagentResultDelivery", "Subagent result delivery"),
    ("max_retries", "Max retries"),
    ("max_turns", "Max turns"),
    ("max_unattended_turns", "Max unattended turns"),
    ("max_history_messages", "Max history messages"),
    ("auto_compact_max_tokens", "Auto compact max tokens"),
    ("auto_compact_min_tokens", "Auto compact min tokens"),
    ("auto_compact_idle_seconds", "Auto compact idle seconds"),
    ("auto_compact_keep_percent", "Auto compact keep percent"),
    ("priority", "Priority"),
    ("inherit_system_prompt", "Inherit system prompt"),
    ("access", "Filesystem access"),
)

_SESSION_SETTING_CHOICES = {
    "precision": ResponseTemperature.choices(),
    "reasoning_effort": ReasoningEffort.choices,
    "scheduler_strategy": TaskSchedulerStrategy.choices,
    "tool_call_syntax": AgentToolCallSyntax.choices,
    "subagentResultDelivery": SubagentResultDelivery.choices,
}
_SESSION_INTEGER_SETTINGS = {
    "max_retries", "max_turns", "max_unattended_turns", "max_history_messages",
    "auto_compact_max_tokens", "auto_compact_min_tokens",
    "auto_compact_idle_seconds", "auto_compact_keep_percent", "priority",
}

#: Cards shown in the Settings tab, in order.  Every field is editable in
#: place (auto-saved on change), so the groups are purely visual.
_SESSION_SETTING_GROUPS = (
    (
        "Behavior",
        (
            "precision",
            "reasoning_effort",
            "scheduler_strategy",
            "tool_call_syntax",
            "subagentResultDelivery",
            "inherit_system_prompt",
        ),
    ),
    (
        "Limits",
        (
            "max_turns",
            "max_unattended_turns",
            "max_history_messages",
            "max_retries",
            "priority",
        ),
    ),
    (
        "Compaction",
        (
            "auto_compact_max_tokens",
            "auto_compact_min_tokens",
            "auto_compact_idle_seconds",
            "auto_compact_keep_percent",
        ),
    ),
    ("Access", ("access",)),
)


def _display_setting(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(getattr(value, "value", value))


def _session_setting_rows(session_model: SessionModel) -> list[dict]:
    try:
        runtime = session_model.get_runtime()
        settings_model = runtime.get_version_model().session_settings
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not load settings for session %s", session_model.pk)
        return []

    rows = []
    for name, label in _SESSION_SETTING_FIELDS:
        try:
            value = getattr(runtime, name)
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("could not resolve setting %s for session %s", name, session_model.pk)
            value = None
        overridden = bool(settings_model and getattr(settings_model, name, None) is not None)
        choices = [
            {"value": str(value), "label": str(label)}
            for value, label in _SESSION_SETTING_CHOICES.get(name, ())
        ]
        rows.append({
            "name": name,
            "label": label,
            "value": _display_setting(value),
            "overridden": overridden,
            "choices": choices,
            "control": (
                "choice" if choices else
                "boolean" if name == "inherit_system_prompt" else
                "integer" if name in _SESSION_INTEGER_SETTINGS else
                "json" if name == "access" else "value"
            ),
        })
    try:
        rows.append({
            "name": "current_turn_count",
            "label": "Current turn count",
            "value": str(runtime.current_turn_count),
            "control": "value",
            "overridden": False,
            "choices": [],
        })
        rows.append({
            "name": "current_unattended_turn_count",
            "label": "Current unattended turns",
            "value": str(runtime.current_unattended_turn_count),
            "control": "value",
            "overridden": False,
            "choices": [],
        })
        rows.append({
            "name": "system_prompt",
            "label": "System prompt",
            "value": runtime.system_prompt or "",
            "control": "text",
            "overridden": False,
            "choices": [],
        })
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not resolve prompt details for session %s", session_model.pk)
    return rows


def _setting_sections(rows: list[dict]) -> list[dict]:
    """Group the session setting rows into readable cards."""
    by_name = {row["name"]: row for row in rows}
    sections = []
    for title, names in _SESSION_SETTING_GROUPS:
        group_rows = [by_name[name] for name in names if name in by_name]
        if not group_rows:
            continue
        sections.append({
            "title": title,
            "rows": group_rows,
            "overridden": sum(1 for row in group_rows if row["overridden"]),
        })
    return sections


def _capability_sections(session_model: SessionModel) -> list[dict]:
    try:
        runtime = session_model.get_runtime()
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not load capabilities for session %s", session_model.pk)
        return []
    sections = []
    for title, allowed_attr, denied_attr in (
        ("Tools", "allowedToolNames", "disallowedToolNames"),
        ("Tasks", "allowedTaskNames", "disallowedTaskNames"),
        ("Commands", "allowedCommandNames", "disallowedCommandNames"),
        ("Skills", "allowedSkillNames", "disallowedSkillNames"),
        ("Subagents", "allowedSubagentNames", "disallowedSubagentNames"),
    ):
        try:
            denied = set(getattr(runtime, denied_attr) or [])
            names = sorted(set(getattr(runtime, allowed_attr) or []) | denied)
            rows = [{"name": name, "allowed": name not in denied} for name in names]
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("could not resolve %s capabilities for session %s", title, session_model.pk)
            rows = []
        allowed_names = [row["name"] for row in rows if row["allowed"]]
        denied_names = [row["name"] for row in rows if not row["allowed"]]
        sections.append({
            "title": title,
            "rows": rows,
            "allowed": allowed_names,
            "denied": denied_names,
            "allowed_count": len(allowed_names),
            "denied_count": len(denied_names),
        })
    return sections


def _workspace_context(session_model: SessionModel, request=None) -> dict:
    """Build the workspace tab context for a chat's bound workspace."""
    try:
        workspace = session_model.latest_session_version.workspace
    except Exception:  # pylint: disable=broad-exception-caught
        workspace = None
    if workspace is None:
        return {"workspace": None}
    raw_path = request.GET.get("path", "") if request is not None else ""

    def browse_url(path):
        return directory_url(
            "webui:chat_panel_tab", [session_model.pk, "workspace"], path
        )

    def push_url(path):
        base = reverse("webui:chat", args=[session_model.pk])
        params = {"panel": "workspace", "path": path}
        return f"{base}?{urlencode(params, safe='/')}"

    context = workspace_tree_context(
        workspace,
        raw_path,
        f"{workspace.pk} session {session_model.pk}",
        surface="panel",
        browse_url=browse_url,
        push_url=push_url,
    )
    return {"workspace": workspace, **context}


def _current_call_tree(session_model: SessionModel) -> dict:
    root = AgentTaskCall.objects.filter(
        session=session_model, session_root_task=F("pk")
    ).order_by("-created_at").first()
    if root is None:
        return {"current_calls": [], "active_call_count": 0}
    calls = list(
        AgentTaskCall.objects.filter(session_root_task=root)
        .select_related("task_definition", "parent_taskrun__agent_task_call")
        .order_by("created_at", "pk")[:500]
    )
    call_by_id = {call.pk: call for call in calls}
    rows = []
    for call in calls:
        parent_run = getattr(call, "parent_taskrun", None)
        parent_call = getattr(parent_run, "agent_task_call", None) if parent_run else None
        depth = 0
        seen = set()
        while parent_call is not None and parent_call.pk in call_by_id and parent_call.pk not in seen:
            depth += 1
            seen.add(parent_call.pk)
            parent_run = getattr(parent_call, "parent_taskrun", None)
            parent_call = getattr(parent_run, "agent_task_call", None) if parent_run else None
        rows.append({
            "call": call,
            "depth": min(depth, 12),
            "name": call.task_definition.name if call.task_definition else f"Call #{call.pk}",
            "status_label": dict(TaskCallStatusDetail.choices).get(
                call.status_detail, str(call.status_detail)
            ),
            "status_color": _CALL_STATUS_COLORS.get(
                call.status_detail, "var(--muted)"
            ),
            "active": call.status != TaskCallStatus.ENDED,
        })
    return {
        "current_calls": rows,
        "active_call_count": sum(1 for row in rows if row["active"]),
    }


def _available_subagents(session_model: SessionModel) -> list[dict]:
    try:
        runtime = session_model.get_runtime()
        parent_name = runtime.agent.name
        return [
            {
                "name": name,
                "parent_name": parent_name,
                "max_turns": runtime.subagent_config(name).get("maxTurns", 0),
            }
            for name in runtime.allowedSubagentNames
        ]
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not list subagents for session %s", session_model.pk)
        return []


@require_POST
def chat_setting(request, session_id: int):
    """Save or reset one whitelisted session setting override."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    name = request.POST.get("name", "")
    action = request.POST.get("action", "set")
    known = {key for key, _label in _SESSION_SETTING_FIELDS}
    if name not in known or action not in ("set", "reset"):
        return HttpResponse("Unknown session setting.", status=400)
    raw = request.POST.get("value", "")
    if action == "reset" or raw == "":
        value = None
    elif name in _SESSION_SETTING_CHOICES:
        choice_values = {str(value) for value, _label in _SESSION_SETTING_CHOICES[name]}
        if raw not in choice_values:
            return HttpResponse("Invalid choice for session setting.", status=400)
        value = float(raw) if name == "precision" else raw
    elif name in _SESSION_INTEGER_SETTINGS:
        try:
            value = int(raw)
        except ValueError:
            return HttpResponse("Enter a whole number.", status=400)
        if value < 0:
            return HttpResponse("Value must not be negative.", status=400)
    elif name == "inherit_system_prompt":
        if raw not in ("true", "false"):
            return HttpResponse("Invalid boolean value.", status=400)
        value = raw == "true"
    elif name == "access":
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return HttpResponse("Filesystem access must be valid JSON.", status=400)
        if value is not None and not isinstance(value, dict):
            return HttpResponse("Filesystem access must be a JSON object.", status=400)
    else:
        return HttpResponse("This session setting is read-only.", status=400)
    try:
        session_model.get_runtime()._set_session_setting(name, value)
        session_model.refresh_from_db(fields=["latest_session_version"])
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not save setting %s for session %s", name, session_id)
        return HttpResponse("Could not save this session setting.", status=500)
    return render(
        request,
        "chats/panels/inner.html",
        _panel_context(session_model, "settings"),
    )


@require_POST
def subagent_open(request, session_id: int):
    session_model = get_object_or_404(SessionModel, pk=session_id)
    name = (request.POST.get("name") or "").strip()
    try:
        runtime = session_model.get_runtime()
        if name not in runtime.allowedSubagentNames:
            return HttpResponse("Subagent is not available in this session.", status=400)
        child = runtime.spawn_subagent(
            name,
            name=f"user-launch:{name}:{datetime.now().strftime('%Y.%m.%d-%H:%M:%S')}",
            description="User-created subagent session",
            session_type=SessionType.SUBSESSION,
            group_key="subagent:manual",
        )
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not open subagent %s for session %s", name, session_id)
        return HttpResponse("Could not start this subagent.", status=500)
    if child is None:
        return HttpResponse("Could not resolve this subagent.", status=400)
    return render(
        request,
        "chats/panels/inner.html",
        _panel_context(session_model, "subagents"),
    )


@require_POST
def subagent_close(request, session_id: int, child_id: int):
    """Mark one active child session closed (keeps it for history)."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    SessionModel.objects.filter(
        pk=child_id, parent_session=session_model
    ).update(is_active=False)
    return render(
        request,
        "chats/panels/inner.html",
        _panel_context(session_model, "subagents", request),
    )


def _template_rows(session_model: SessionModel) -> list[dict]:
    """Session-scoped query templates for the Templates panel tab."""
    from runtime.query_templates import list_templates

    try:
        return list_templates(session_model.pk)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not list templates for session %s", session_model.pk)
        return []


def _template_run_state(session_model: SessionModel) -> dict:
    """Read the last template run dispatched from this session, if any."""
    state = cache.get(_template_run_key(session_model.pk))
    if not state:
        return {}
    call_pk = state.get("call_pk")
    if not call_pk:
        return state
    call = AgentTaskCall.objects.filter(pk=call_pk).first()
    if call is None:
        return {"name": state.get("name", ""), "status": "call not found", "content": ""}
    try:
        result = call.get_result(timeout=0)
    except TimeoutError:
        return {
            "name": state.get("name", ""),
            "status": f"running ({call.status_detail})",
            "content": "",
        }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return {"name": state.get("name", ""), "status": "ended", "content": str(exc)}
    if not isinstance(result, dict):
        result = {"content": str(result)}
    status = result.get("status", "")
    return {
        "name": state.get("name", ""),
        "status": "done" if status == "SUCCESS" else f"ended ({status})",
        "content": result.get("content") or result.get("error") or "",
        "model": result.get("model", ""),
    }


def _read_todos(session_model: SessionModel) -> list[dict]:
    """Read the session's event-sourced todo list (best effort)."""
    try:
        runtime = session_model.get_runtime()
        anchor = runtime.get_task("todolist_action") or runtime.get_tool(
            "todolist_action"
        )
        raw = anchor.lastest_result() if anchor is not None else None
    except Exception:  # pylint: disable=broad-exception-caught
        return []
    items = raw.get("items", []) if isinstance(raw, dict) else []
    return [item for item in items if isinstance(item, dict)]


def _search_history(session_model: SessionModel, request=None) -> dict:
    """Search the session's own history using the search_own_history tool."""
    try:
        runtime = session_model.get_runtime()
        tool = runtime.get_tool("search_own_history")
        if tool is None:
            return {"error": "History search tool not available.", "results": [], "total_count": 0}
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not get history search tool for session %s", session_model.pk)
        return {"error": "Could not initialize history search.", "results": [], "total_count": 0}

    # Get query parameters from request
    text = ""
    role = ""
    part_type = ""
    tool_call_name = ""
    include_compacted = False  # Default: resolved view (show resolved only)
    include_hidden = False
    include_subsessions = False
    limit = 20
    offset = 0
    order = "newest"
    date_from = ""
    date_to = ""

    if request and request.GET:
        text = request.GET.get("q", "") or ""
        role = request.GET.get("role", "") or ""
        part_type = request.GET.get("part_type", "") or ""
        tool_call_name = request.GET.get("tool_call_name", "") or ""
        # resolved_view=True (default) -> include_compacted=False (show resolved only)
        # resolved_view=False -> include_compacted=True (show all including compacted)
        resolved_view = request.GET.get("resolved_view", "true").lower() == "true"
        include_compacted = not resolved_view
        include_hidden = request.GET.get("include_hidden", "false").lower() == "true"
        include_subsessions = request.GET.get("include_subsessions", "false").lower() == "true"
        try:
            limit = int(request.GET.get("limit", "20"))
        except ValueError:
            limit = 20
        try:
            offset = int(request.GET.get("offset", "0"))
        except ValueError:
            offset = 0
        order = request.GET.get("order", "newest")
        date_from = request.GET.get("date_from", "") or ""
        date_to = request.GET.get("date_to", "") or ""

    # Call the tool using BoundTask.call()
    result = tool.call(
        text=text if text else None,
        role=role if role else None,
        part_type=part_type if part_type else None,
        tool_call_name=tool_call_name if tool_call_name else None,
        include_hidden=include_hidden,
        include_compacted=include_compacted,
        include_subsessions=include_subsessions,
        limit=limit,
        offset=offset,
        order=order,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
    )

    # Add query parameters back for the template
    result["query"] = {
        "q": text,
        "role": role,
        "part_type": part_type,
        "tool_call_name": tool_call_name,
        "resolved_view": not include_compacted,
        "include_hidden": include_hidden,
        "include_subsessions": include_subsessions,
        "limit": limit,
        "offset": offset,
        "order": order,
        "date_from": date_from,
        "date_to": date_to,
    }
    # Paging URL for "Load more": rebuild it from the current filters instead of
    # appending to request.GET, whose old ``offset`` would win over the new one.
    next_offset = result.get("next_offset") or 0
    if request is not None:
        params = request.GET.copy()
        params.pop("offset", None)
        params["offset"] = str(next_offset)
        result["next_query"] = params.urlencode()
    else:
        result["next_query"] = f"offset={next_offset}"
    try:
        result["remaining"] = max(
            int(result.get("total_count") or 0) - int(next_offset), 0
        )
    except (TypeError, ValueError):
        result["remaining"] = 0
    return result


@require_POST
def call_cancel(request, session_id: int, call_id: int):
    """Cancel an active task call belonging to the current session."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    call = get_object_or_404(AgentTaskCall, pk=call_id, session=session_model)
    if call.status != TaskCallStatus.ENDED:
        from server.tasks.recovery_scheduler import _force_end_call

        try:
            _force_end_call(call)
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("could not cancel call %s for session %s", call_id, session_id)
            return HttpResponse("Could not cancel this task call.", status=500)
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "chats/panels/inner.html",
            _panel_context(session_model, "calls", request),
        )
    return redirect(f"/app/chat/{session_model.pk}?panel=calls")


@require_POST
def chat_todo_action(request, session_id: int):
    """Control automatic todo processing or clear the session todo list."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    action = request.POST.get("action", "")
    if action not in ("auto", "pause", "clear"):
        return HttpResponse("Unknown todo action.", status=400)
    try:
        runtime = session_model.get_runtime()
        if action in ("auto", "pause"):
            runtime._set_session_setting("todo_auto_process", action == "auto")
        else:
            anchor = runtime.get_task("todolist_action") or runtime.get_tool(
                "todolist_action"
            )
            if anchor is None:
                return HttpResponse("No todo list is available to clear.", status=409)
            anchor.delay(action="clear")
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("todo action %s failed for session %s", action, session_id)
        return HttpResponse("Could not update the todo list.", status=500)
    if request.headers.get("HX-Request") == "true":
        context = _panel_context(session_model, "todos", request)
        context["todo_action_message"] = (
            "Todo clear requested." if action == "clear" else ""
        )
        return render(request, "chats/panels/inner.html", context)
    return redirect(f"/app/chat/{session_model.pk}?panel=todos")


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

@require_POST
def call_action(request, call_id: int):
    """Approve/deny a halted call, or answer an ``ask_user`` question."""
    call = get_object_or_404(
        AgentTaskCall.objects.select_related("session", "task_definition"),
        pk=call_id,
    )
    action = request.POST.get("action", "")
    feedback = (request.POST.get("feedback") or "").strip()
    from runtime.tasks.call_scheduler import CallScheduler

    try:
        if action == "approve":
            CallScheduler.approve_taskcall(call.pk)
        elif action in ("deny", "decline"):
            CallScheduler.deny_taskcall(call.pk, feedback=feedback)
        elif action == "answer":
            _answer_question(call, request.POST)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("call action %s failed for call %s", action, call_id)

    # Return the appropriate card partial based on the call type
    from server.models.enums.task_enums import TaskCallStatusDetail
    
    call.refresh_from_db()
    if call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL:
        # Still halted - show updated approval card
        context = session_context(call.session)
        return render(request, "chats/parts/approval_card.html", context)
    elif call.status_detail == TaskCallStatusDetail.WAITING_QUEUE:
        # Was answered - show updated question card
        context = session_context(call.session)
        return render(request, "chats/parts/question_card.html", context)
    else:
        # Call was processed - return empty to remove the card
        return HttpResponse("")


def _answer_question(call: AgentTaskCall, post) -> None:
    """Merge one question's answer into a halted ``ask_user`` call."""
    from runtime.tasks.call_scheduler import CallScheduler
    from runtime.user_questions import normalize_questions

    args = call.carguments_json or {}
    # Resolve any GenericContent references in the stored arguments
    args = resolve_generic_content_refs(args)
    questions = normalize_questions(args.get("questions"))
    raw_index = post.get("qidx", "")
    if not raw_index.isdigit():
        return
    qidx = int(raw_index)
    if not 0 <= qidx < len(questions):
        return

    options = questions[qidx]["options"]
    labels: list[str] = []
    for raw in post.getlist("option"):
        if not raw.isdigit():
            continue
        oidx = int(raw)
        if 0 <= oidx < len(options):
            labels.append(options[oidx]["label"])
    other = (post.get("other") or "").strip()
    if other:
        labels.append(other)
    if not labels:
        return

    answer = labels if questions[qidx]["multiSelect"] else labels[0]
    CallScheduler.answer_question_call(
        call.pk, {questions[qidx]["question"]: answer}
    )


@require_POST
def queue_action(request, session_id: int):
    """Cancel, clear or combine queued user messages."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    action = request.POST.get("action", "")
    queued = (
        AgentTaskCall.objects.filter(
            session=session_model,
            status_detail=TaskCallStatusDetail.WAITING_QUEUE,
        )
        .select_related("task_definition", "task_definition_version__task_definition")
        .order_by("created_at")
    )
    queued = [call for call in queued if queue_text(call) is not None and getattr(call, "task_definition", None) and getattr(call.task_definition, "name", "") == "ingest_user_message"]
    # Fall back to versioned definition name for calls without direct definition name.
    if not queued:
        queued = [
            call
            for call in AgentTaskCall.objects.filter(
                session=session_model,
                status_detail=TaskCallStatusDetail.WAITING_QUEUE,
            )
            .select_related("task_definition", "task_definition_version__task_definition")
            .order_by("created_at")
            if (
                (getattr(call, "task_definition", None) and call.task_definition.name == "ingest_user_message")
                or (
                    getattr(call, "task_definition_version", None)
                    and call.task_definition_version.task_definition
                    and call.task_definition_version.task_definition.name == "ingest_user_message"
                )
            )
        ]

    try:
        if action == "cancel":
            raw_call = request.POST.get("call_id", "")
            if raw_call.isdigit():
                target = int(raw_call)
                for call in queued:
                    if call.pk == target:
                        AgentTaskCall.objects.filter(pk=target).delete()
                        break
        elif action == "clear":
            ids = [call.pk for call in queued]
            if ids:
                AgentTaskCall.objects.filter(pk__in=ids).delete()
        elif action == "combine":
            texts = [queue_text(call) for call in queued]
            ids = [call.pk for call in queued]
            if ids:
                AgentTaskCall.objects.filter(pk__in=ids).delete()
            combined = "\n\n".join(text for text in texts if text).strip()
            if combined:
                session_model.get_runtime().add_user_message(combined)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("queue action %s failed for session %s", action, session_id)

    context = session_context(session_model)
    return render(request, "chats/parts/queue_card.html", context)


@require_POST
def turn_approval(request, session_id: int):
    """Reset the unattended-turn counters and optionally resume the turn."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    action = request.POST.get("action", "approve")
    try:
        runtime = session_model.get_runtime()
        runtime.reset_turn_count()
        runtime.reset_unattended_turn_count()
        if action != "deny":
            last_message = session_model.related_messages.order_by("-pk").first()
            if last_message is not None:
                runtime.get_task("process_turn").delay(message=last_message)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("turn approval failed for session %s", session_id)

    context = session_context(session_model)
    return render(request, "chats/parts/turnlimit_card.html", context)


@require_POST
def ratelimit_action(request, session_id: int):
    """Retry or switch away from the blocked model/key for a parked call."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    action = request.POST.get("action", "retry")
    try:
        runtime = session_model.get_runtime()
        if action == "switch-key":
            from server.models.providers.api_key import ApiKey

            raw_key = (request.POST.get("key") or "").strip()
            key = ApiKey.objects.filter(pk=int(raw_key)).first() if raw_key.isdigit() else None
            if key is not None:
                runtime.set_preferred_api_key(key)
        elif action == "switch-provider":
            raw_provider = (request.POST.get("provider") or "").strip()
            blocked = runtime.aimodel
            if blocked is not None and raw_provider.isdigit():
                runtime.set_aimodel_by_provider(blocked.name, int(raw_provider))
        elif action == "switch-model":
            name = (request.POST.get("model") or "").strip()
            if name:
                runtime.set_aimodel_by_name(name)
        elif action == "toggle-failover":
            runtime.set_auto_failover_keys(not runtime.auto_failover_keys_enabled())
        elif action == "max-wait":
            raw_seconds = (request.POST.get("seconds") or "").strip()
            seconds = int(raw_seconds) if raw_seconds.isdigit() else 0
            if seconds != runtime.key_max_wait_seconds():
                runtime.set_key_max_wait_seconds(seconds or None)

        from runtime.tasks.call_scheduler import CallScheduler

        CallScheduler.release_waiting_ratelimit_calls(session_model, repoint=True)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("rate-limit action %s failed for session %s", action, session_id)

    context = session_context(session_model)
    return render(request, "chats/parts/ratelimit_card.html", context)


@require_POST
def chat_config(request, session_id: int):
    """Persist composer model / reasoning / workspace overrides."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    try:
        runtime = session_model.get_runtime()
        if "name" in request.POST:
            name = (request.POST.get("name") or "").strip()
            if name and name != session_model.name:
                session_model.name = name
                session_model.save(update_fields=["name"])
                version = session_model.latest_session_version
                if version is not None:
                    version.display_name = name
                    version.save(update_fields=["display_name"])
        if "model" in request.POST:
            model_name = (request.POST.get("model") or "").strip()
            if model_name:
                runtime.set_aimodel_by_name(model_name)
            else:
                runtime.set_aimodel(None)
        if "reasoning" in request.POST:
            value = (request.POST.get("reasoning") or ReasoningEffort.NONE).strip()
            if value in {choice for choice, _ in ReasoningEffort.choices}:
                runtime.set_reasoning_effort(value)
        if "agent" in request.POST:
            raw_agent = (request.POST.get("agent") or "").strip()
            agent = (
                AgentModel.objects.filter(pk=int(raw_agent), is_archived=False).first()
                if raw_agent.isdigit()
                else None
            )
            if agent is not None:
                runtime.set_agent(agent)
        if "workspace" in request.POST:
            raw = (request.POST.get("workspace") or "").strip()
            workspace = (
                WorkspaceModel.objects.filter(pk=int(raw)).first()
                if raw.isdigit()
                else None
            )
            runtime.set_workspace(workspace)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("composer config failed for session %s", session_id)
    panel = (request.POST.get("panel") or "").strip()
    if (request.POST.get("composer") or "").strip() == "1":
        session_model.refresh_from_db()
        context = {"session": session_model}
        context.update(composer_config(session_model))
        return render(request, "chats/parts/composer_config.html", context)
    if request.headers.get("HX-Request") == "true" or panel:
        session_model.refresh_from_db()
        return render(
            request,
            "chats/panels/inner.html",
            _panel_context(session_model, panel or "settings", request),
        )
    return redirect("webui:chat", session_id=session_id)


@require_POST
def fork_chat(request, session_id: int):
    """Fork the conversation at a message (permanent user branch)."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    raw = request.POST.get("message_id", "")
    message = (
        Message.objects.filter(pk=int(raw), session=session_model).first()
        if raw.isdigit()
        else None
    )
    if message is None:
        return redirect("webui:chat", session_id=session_id)
    try:
        runtime = session_model.get_runtime()
        if runtime.agent.get_version_model() is None:
            return redirect("webui:chat", session_id=session_id)
        child = runtime.fork(
            name=f"p{session_model.pk}:fork:{datetime.now().strftime('%Y.%m.%d-%H:%M:%S')}",
            description=f"Forked from message #{message.pk}",
            session_type=SessionType.SESSION,
            group_key="chat:fork",
            anchor=message,
        )
        return redirect("webui:chat", session_id=child.model.pk)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("fork failed for session %s message %s", session_id, raw)
        return redirect("webui:chat", session_id=session_id)


@require_POST
def edit_message(request, session_id: int, message_id: int):
    """Rewrite a user message, drop the turns after it, and rerun the turn."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    message = Message.objects.filter(
        pk=message_id, session=session_model, role="user"
    ).first()
    text = (request.POST.get("text") or "").strip()
    if message is None or not text:
        return redirect("webui:chat", session_id=session_id)

    try:
        part = (
            message.parts.filter(content_type="TEXT", type="MESSAGE")
            .order_by("pk")
            .first()
        )
        if part is None:
            message.add_part("MESSAGE", "TEXT", text)
        else:
            part.content = GenericContent.from_text(text)
            part.save(update_fields=["content"])
        # Editing a prompt invalidates every later turn; drop them before the
        # rerun so the context is exactly what the user now sees.
        Message.objects.filter(session=session_model, pk__gt=message.pk).delete()
        runtime = session_model.get_runtime()
        runtime.reset_turn_count()
        runtime.reset_unattended_turn_count()
        runtime.get_task("process_turn").delay(message=message)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("edit message %s failed for session %s", message_id, session_id)
    return redirect("webui:chat", session_id=session_id)


@require_POST
def clear_conversation(request, session_id: int):
    """Delete every message and query in this conversation (keeps the chat)."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    try:
        Message.objects.filter(session=session_model).delete()
        Query.objects.filter(session=session_model).delete()
        Response.objects.filter(session=session_model).delete()
        runtime = session_model.get_runtime()
        runtime.reset_turn_count()
        runtime.reset_unattended_turn_count()
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("clear conversation failed for session %s", session_id)
    return redirect("webui:chat", session_id=session_id)


@require_POST
def import_conversation(request, session_id: int):
    """Import messages from a JSON export into this conversation."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    upload = request.FILES.get("file")
    if upload is None:
        return redirect("webui:chat", session_id=session_id)
    try:
        payload = json.loads(upload.read().decode("utf-8"))
        messages = payload.get("messages", []) if isinstance(payload, dict) else payload
        if not isinstance(messages, list):
            raise ValueError("expected a list of messages")
        version = session_model.latest_session_version
        previous = session_model.related_messages.order_by("-pk").first()
        for spec in messages[:5000]:
            if not isinstance(spec, dict):
                continue
            created = Message.objects.create(
                role=spec.get("role") or "user",
                message_type=spec.get("message_type") or "default",
                session=session_model,
                session_version=version,
                prev_message=previous,
            )
            for part in spec.get("parts") or []:
                if not isinstance(part, dict):
                    continue
                if str(part.get("type", "")).upper() == "TOOLCALL":
                    continue
                content = part.get("content", "")
                if not isinstance(content, str):
                    content = json.dumps(content, ensure_ascii=False, default=str)
                created.add_part(
                    type=part.get("type") or "MESSAGE",
                    content_type=part.get("content_type") or "TEXT",
                    content=content,
                )
            created.publish("create")
            previous = created
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("import conversation failed for session %s", session_id)
    return redirect("webui:chat", session_id=session_id)


def chat_transcript(request, session_id: int):
    """Download the conversation as Markdown."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    rows = build_thread(session_model, limit=5000)
    lines = [f"# {session_model.name}", ""]
    for row in rows:
        if row.kind != "message":
            continue
        role = {
            "user": "user",
            "assistant": "assistant",
            "info": "info",
            "system": "system",
        }.get(row.role, row.role.lower())
        text = row.body_text.strip()
        if not text:
            continue
        lines.extend([f"## {role}", "", text, ""])
        # Include tool calls if present
        if row.tools:
            for tool in row.tools:
                tool_name = tool.get("name", "tool")
                tool_status = tool.get("status_detail") or tool.get("status") or "unknown"
                tool_body = tool.get("body", "")
                lines.extend([
                    f"### Tool: {tool_name}",
                    f"Status: {tool_status}",
                    "",
                    "```",
                    tool_body,
                    "```",
                    ""
                ])
    response = HttpResponse("\n".join(lines), content_type="text/markdown; charset=utf-8")
    filename = _safe_filename(session_model.name or f"chat-{session_model.pk}")
    response["Content-Disposition"] = f'attachment; filename="{filename}.md"'
    return response


def chat_export(request, session_id: int):
    """Download the full session (messages + parts) as JSON."""
    from server.models.enums.message_enums import MessagePartType
    
    session_model = get_object_or_404(SessionModel, pk=session_id)
    messages = (
        Message.objects.filter(session=session_model)
        .select_related("response")
        .prefetch_related("parts")
        .order_by("pk")
    )
    payload = {
        "session": {
            "pk": session_model.pk,
            "name": session_model.name,
            "created_at": _iso(session_model.created_at),
            "updated_at": _iso(session_model.updated_at),
        },
        "messages": [
            {
                "pk": message.pk,
                "role": message.role,
                "message_type": message.message_type,
                "created_at": _iso(message.created_at),
                "parts": [
                    {
                        "type": part.type,
                        "content_type": part.content_type,
                        "content": _part_content(part),
                    }
                    for part in message.parts.all()
                    # Exclude reasoning/reflection parts
                    if part.type != MessagePartType.REASONING
                ],
            }
            for message in messages
        ],
    }
    response = HttpResponse(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        content_type="application/json; charset=utf-8",
    )
    filename = _safe_filename(session_model.name or f"chat-{session_model.pk}")
    response["Content-Disposition"] = f'attachment; filename="{filename}.json"'
    return response


def _iso(value) -> str:
    return value.isoformat() if value is not None else ""


def _part_content(part) -> str:
    try:
        return part.content.get() if part.content_id else ""
    except Exception:  # pylint: disable=broad-exception-caught
        return ""


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name or "").strip("-")
    return cleaned[:80] or "chat"


def _int_param(raw) -> int | None:
    return int(raw) if isinstance(raw, str) and raw.isdigit() else None


def _panel_response(request, session_model: SessionModel, tab: str):
    return render(
        request,
        "chats/panels/inner.html",
        _panel_context(session_model, tab),
    )


def _template_inputs(session_model: SessionModel, name: str, post):
    """Load *name* and collect its declared variables from the POST body."""
    from runtime.query_templates import get_template

    template = get_template(session_model.pk, name)
    variables = {
        variable.name: post.get(f"var_{variable.name}", "")
        for variable in template.variables
    }
    return template, variables


@require_POST
def template_preview(request, session_id: int):
    """Render a query template without dispatching it."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    name = (request.POST.get("name") or "").strip()
    try:
        from runtime.query_templates import render_template_by_name

        template, variables = _template_inputs(session_model, name, request.POST)
        _, rendered = render_template_by_name(session_model.pk, name, variables)
        cache.set(
            _template_preview_key(session_model.pk),
            {"name": template.name, "text": rendered},
            _TEMPLATE_PREVIEW_TTL,
        )
        cache.delete(_template_error_key(session_model.pk))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        cache.set(_template_error_key(session_model.pk), str(exc), _TEMPLATE_PREVIEW_TTL)
    return _panel_response(request, session_model, "templates")


@require_POST
def template_run(request, session_id: int):
    """Render a template and dispatch ``call_llm_direct`` for it."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    name = (request.POST.get("name") or "").strip()
    try:
        from runtime.query_templates import render_template_by_name

        template, variables = _template_inputs(session_model, name, request.POST)
        _, rendered = render_template_by_name(session_model.pk, name, variables)
        task = session_model.get_runtime().get_task("call_llm_direct")
        if task is None:
            raise RuntimeError("Task 'call_llm_direct' is not available for this session.")
        call = task.delay(messages=[{"role": "user", "content": rendered}], model_name=None)
        cache.set(
            _template_run_key(session_model.pk),
            {
                "name": template.name,
                "call_pk": getattr(call, "pk", None),
                "rendered": rendered,
            },
            _TEMPLATE_RUN_TTL,
        )
        cache.delete(_template_error_key(session_model.pk))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        cache.set(_template_error_key(session_model.pk), str(exc), _TEMPLATE_PREVIEW_TTL)
    return _panel_response(request, session_model, "templates")


@require_POST
def template_delete(request, session_id: int):
    """Delete a session template link."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    name = (request.POST.get("name") or "").strip()
    try:
        from runtime.query_templates import delete_template

        delete_template(session_model.pk, name)
        cache.delete(_template_preview_key(session_model.pk))
        cache.delete(_template_run_key(session_model.pk))
        cache.delete(_template_error_key(session_model.pk))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        cache.set(_template_error_key(session_model.pk), str(exc), _TEMPLATE_PREVIEW_TTL)
    return _panel_response(request, session_model, "templates")


def _thread_response(request, session_model: SessionModel):
    """Render the thread fragment after an in-place action."""
    context = session_context(session_model)
    context["send_key"] = send_key()
    return render(request, "chats/parts/thread_inner.html", context)


@require_POST
def send_message(request, session_id: int):
    session_model = get_object_or_404(SessionModel, pk=session_id)
    text = (request.POST.get("text") or "").strip()
    action = (request.POST.get("action") or "send").strip()
    context = session_context(session_model)
    context["send_key"] = send_key()

    if action == "stop":
        try:
            session_model.get_runtime().stop_generation()
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("could not stop session %s", session_id)
        return render(request, "chats/parts/thread_inner.html", context)

    image_parts = _image_parts(request.POST.get("images"))
    if not text and not image_parts:
        return render(request, "chats/parts/thread_inner.html", context)

    parts = list(image_parts)
    if text:
        parts.append({"type": "MESSAGE", "content_type": "TEXT", "content": text})

    try:
        runtime = session_model.get_runtime()
        if action == "queue":
            runtime.queue_message(parts)
        elif action == "interrupt":
            runtime.stop_generation()
            runtime.add_user_message(parts, force=True)
        elif action == "steer":
            runtime.steer_message(parts)
        else:
            runtime.add_user_message(parts)
        # Persistence happens in Celery, so show an optimistic bubble until
        # the Message.create event triggers the real refetch.
        context["pending_text"] = text
        context["pending_images"] = [part["content"] for part in image_parts]
    except Exception as exc:  # pylint: disable=broad-exception-caught
        log.exception("could not send message to session %s", session_id)
        context["send_error"] = str(exc)

    return render(request, "chats/parts/thread_inner.html", context)


def _image_parts(raw: str | None) -> list[dict]:
    """Decode the composer's hidden ``images`` JSON into IMAGE message parts.

    The browser downscales each image and sends a data URI; anything that is
    not a ``data:image/*`` string is ignored so the field cannot be used to
    inject arbitrary content.
    """
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(items, list):
        return []
    parts: list[dict] = []
    for item in items[:6]:
        content = item.get("content") if isinstance(item, dict) else item
        if isinstance(content, str) and content.startswith("data:image/"):
            parts.append(
                {"type": "MESSAGE", "content_type": "IMAGE", "content": content}
            )
    return parts


@require_POST
def new_chat(request):
    raw_agent = (request.POST.get("agent") or "").strip()
    agent = (
        AgentModel.objects.filter(pk=int(raw_agent), is_archived=False).first()
        if raw_agent.isdigit()
        else None
    )
    if agent is None:
        agent = default_agent()
    if agent is None:
        return redirect("/app/?error=no-agent")

    raw_workspace = (request.POST.get("workspace") or "").strip()
    workspace = (
        WorkspaceModel.objects.filter(pk=int(raw_workspace)).first()
        if raw_workspace.isdigit()
        else None
    )
    description = (request.POST.get("description") or "").strip()
    requested_name = (request.POST.get("name") or "").strip()
    name = requested_name or unique_session_name(f"{agent.name}-chat")
    if SessionModel.objects.filter(name=name).exists():
        name = unique_session_name(name)
    try:
        session_version = agent.latest_agent_version.get_or_create_session(
            name=name,
            display_name=name,
            description=description,
            workspace=workspace,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("could not create chat for agent %s", agent.name)
        return redirect("/app/?error=create-failed")

    return redirect("webui:chat", session_id=session_version.session_id)


@require_POST
def chat_action(request, session_id: int):
    """Apply a small session action and bounce back to the chat."""
    session_model = get_object_or_404(SessionModel, pk=session_id)
    action = request.POST.get("action", "")
    runtime = None
    try:
        runtime = session_model.get_runtime()
    except Exception:  # pylint: disable=broad-exception-caught
        runtime = None

    try:
        if action == "stop" and runtime is not None:
            runtime.stop_generation()
        elif action == "pause" and runtime is not None:
            runtime.pause()
        elif action == "resume" and runtime is not None:
            runtime.resume()
        elif action == "upgrade_agent" and runtime is not None:
            runtime.upgrade_to_latest_agent()
        elif action == "pin":
            session_model.is_pinned = not session_model.is_pinned
            session_model.save(update_fields=["is_pinned"])
        elif action == "archive":
            session_model.is_archived = True
            session_model.save(update_fields=["is_archived", "is_active"])
            if request.headers.get("HX-Request") == "true":
                return HttpResponse(headers={"HX-Redirect": reverse("webui:chats")})
            return _chat_action_redirect(request, session_model, fallback="chats")
        elif action == "unarchive":
            session_model.is_archived = False
            session_model.is_active = True
            session_model.save(update_fields=["is_archived", "is_active"])
        elif action == "rename":
            name = (request.POST.get("name") or "").strip()
            if name:
                session_model.name = name
                session_model.save(update_fields=["name"])
                version = session_model.latest_session_version
                if version is not None:
                    version.display_name = name
                    version.save(update_fields=["display_name"])
        elif action == "move":
            from server.models.project import Project

            raw_project = (request.POST.get("project") or "").strip()
            project = (
                Project.objects.filter(pk=int(raw_project)).first()
                if raw_project.isdigit()
                else None
            )
            session_model.parent_project = project
            session_model.save(update_fields=["parent_project"])
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("chat action %s failed for session %s", action, session_id)

    if request.headers.get("HX-Request") == "true":
        surface = (request.POST.get("surface") or "").strip()
        if surface == "header":
            session_model.refresh_from_db()
            return render(
                request, "chats/parts/header.html", _header_context(session_model)
            )
        if surface == "panel":
            session_model.refresh_from_db()
            tab = (request.POST.get("panel") or "details").strip()
            return render(
                request,
                "chats/rightbar_body.html",
                _panel_context(session_model, tab, request),
            )
        if surface == "sidebar":
            # The sidebar is a live component; its own observable keys refetch
            # it after the model write.  No HTML is returned here so the POST
            # never races the SSE-driven refresh.
            return HttpResponse(status=204)

    return _chat_action_redirect(request, session_model)


def _chat_action_redirect(request, session_model: SessionModel, fallback=None):
    """Return to the page that submitted the action, if it is in-app."""
    nxt = (request.POST.get("next") or "").strip()
    if nxt.startswith("/app/") and "\r" not in nxt and "\n" not in nxt:
        return redirect(nxt)
    if fallback:
        return redirect(f"webui:{fallback}")
    return redirect("webui:chat", session_id=session_model.pk)
