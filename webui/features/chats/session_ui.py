"""Chat/session UI helpers (thread, composer, usage, commands)."""

from __future__ import annotations

import logging

from django.urls import reverse

from server.models.message import Message
from server.models.sessions.session import SessionModel
from server.models.settings import ReasoningEffort
from webui.features.chats.parts.thread import DEFAULT_LIMIT, build_thread

log = logging.getLogger(__name__)

_RING_CIRCUMFERENCE = 2 * 3.141592653589793 * 9.75


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


def composer_config(
    session_model: SessionModel,
    model_filter: str | None = None,
    search: str = "",
) -> dict:
    from runtime.session.aimodel_picker import model_groups
    from server.models.agents.agent import AgentModel
    from server.models.providers.ai_model_offering import AiModelOffering
    from server.models.workspace import WorkspaceModel

    if model_filter not in ("favorites", "free", "local", "all"):
        model_filter = None

    context: dict = {
        "composer_model": "",
        "composer_models": [],
        "composer_model_names": [],
        "composer_model_filter": model_filter or "favorites",
        "composer_model_filters": [
            ("favorites", "Favorites"),
            ("free", "Free"),
            ("local", "Local"),
            ("all", "All models"),
        ],
        "composer_has_favorites": False,
        "composer_model_favorite": False,
        "composer_provider": "",
        "composer_key": "",
        "composer_route_label": "",
        "composer_agent_id": None,
        "composer_agents": [],
        "composer_reasoning": ReasoningEffort.NONE,
        "composer_reasoning_choices": ReasoningEffort.choices,
        "composer_workspace_id": None,
        "composer_workspaces": [],
        # Agent/workspace are only chosen while the session is still pristine.
        # Once the first turn runs, switching either would re-pin the version
        # and throw away the context cache.
        "composer_setup_editable": False,
    }
    try:
        context["composer_setup_editable"] = not session_model.related_messages.exists()
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        runtime = session_model.get_runtime()
    except Exception:  # pylint: disable=broad-exception-caught
        return context
    try:
        current = runtime.aimodel
        context["composer_model"] = current.name if current is not None else ""
        if current is not None:
            context["composer_provider"] = getattr(
                getattr(current, "api_provider", None), "name", ""
            ) or ""
            context["composer_model_favorite"] = bool(
                getattr(getattr(current, "model", None), "is_favorite", False)
            )
        route = runtime.get_route()
        key = getattr(route, "api_key", None) if route is not None else None
        if key is not None:
            context["composer_key"] = key.comment or f"key {key.pk}"
        elif current is not None and getattr(
            getattr(current, "api_provider", None), "default_api_key", ""
        ):
            context["composer_key"] = "built-in"
        intent = runtime.route_intent()
        context["composer_route_label"] = intent.label
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
        has_favorites = AiModelOffering.objects.filter(
            enabled=True, model__is_favorite=True
        ).exists()
        context["composer_has_favorites"] = has_favorites
        if model_filter is None:
            context["composer_model_filter"] = "favorites" if has_favorites else "all"
        groups = model_groups(
            favorites_only=context["composer_model_filter"] == "favorites",
            free_only=context["composer_model_filter"] == "free",
            local_only=context["composer_model_filter"] == "local",
            search=search,
        )
        context["composer_models"] = [
            {
                "name": group.name,
                "favorite": group.is_favorite,
                "free": group.is_free,
                "bars": group.bars,
                "rank": group.rank,
                "tier": group.tier,
                "providers": group.provider_count,
            }
            for group in groups
        ]
        context["composer_model_names"] = [row["name"] for row in context["composer_models"]]
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
