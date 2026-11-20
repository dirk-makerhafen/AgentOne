"""Chat/session UI helpers (thread, composer, usage, commands)."""

from __future__ import annotations

import logging

from django.urls import reverse

from server.models.message import Message
from server.models.sessions.session import SessionModel
from server.models.settings import ReasoningEffort
from webui.features.chats.parts.cards import build_chat_cards
from webui.features.chats.parts.thread import DEFAULT_LIMIT, build_thread

log = logging.getLogger(__name__)

_RING_CIRCUMFERENCE = 2 * 3.141592653589793 * 9.75


def is_busy(session_model: SessionModel) -> bool:
    try:
        return bool(session_model.get_runtime().is_busy())
    except Exception:  # pylint: disable=broad-exception-caught
        return False


def thread_triggers(session_pk: int) -> str:
    keys = [
        f"Message.session:{session_pk}",
        f"Query.session:{session_pk}",
        f"Response.session:{session_pk}",
        f"AgentTaskCall.session:{session_pk}",
        f"SessionModel:{session_pk}",
    ]
    return ", ".join(f"sse:{key} delay:150ms" for key in keys)


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
        # Thread fragments rendered directly (send, actions, legacy endpoints) should
        # return complete message content, not placeholders that fan out per child.
        "component_inline": True,
    }


def _fmt_tokens(value) -> str:
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
    from runtime.session.aimodel_picker import model_groups
    from server.models.agents.agent import AgentModel
    from server.models.workspace import WorkspaceModel

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
            AgentModel.objects.filter(is_archived=False, parent_agent__isnull=True).order_by("name")
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
        context["composer_workspaces"] = list(WorkspaceModel.objects.order_by("name").only("pk", "name", "path"))
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    return context


def composer_state(session_model: SessionModel) -> dict:
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
