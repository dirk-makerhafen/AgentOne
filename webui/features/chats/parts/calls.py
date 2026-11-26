"""Presentation helpers for the AgentTaskCall / AgentTaskRun graph.

The runtime records three different relationships between calls, and the UI
must not flatten them into one confusing indentation ladder:

``parent_taskrun``
    "This call was created while that run was executing."  A turn loop uses
    this for every next ``process_turn``, so it is *not* a reliable nesting
    signal by itself.

``taskcall_arg_references`` / ``taskrun_arg_references``
    "This call needs the result of those calls before it can run."

``taskrun_result_references``
    "This call's result contains those calls, and the run waits for them."
    This is the async-return path (``return other_task.delay(...)``).

A call can also cross a session boundary (``delegate_task``, ``spawn_subtask``,
``message_subsession``, ...).  Those child sessions are useful destinations,
but their internal framework pipeline is not useful noise in the parent's call
list.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from functools import lru_cache
from typing import Any, Iterable

from django.apps import apps
from django.db.models import Count, Prefetch
from django.urls import reverse
from django.utils import timezone

from server.models.content import GenericContent
from server.models.enums.message_enums import MessagePartType
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail, TaskType
from server.models.message import MessagePart
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun

#: Core tasks that are plumbing for one LLM step.  They are hidden from the
#: default call views; ``map`` is core but is a real fan-out operation.
VISIBLE_CORE_TASKS = frozenset({"map"})

#: Framework tasks that live outside the ``core`` group (or have several
#: definitions, one of which is not core).
FRAMEWORK_TASK_NAMES = frozenset(
    {
        "auto_title_session",
        "bootstrap_session",
        "build_llm_compact_context",
        "build_llm_context",
        "call_llm",
        "call_llm_direct",
        "catch_approval_denied",
        "catch_tool_argument_error",
        "compact_if_needed",
        "compact_turn",
        "decide_next_step",
        "handle_slashcommand_response",
        "ingest_assistant_message",
        "ingest_auto_title",
        "ingest_compaction",
        "ingest_slash_command",
        "ingest_subagent_result",
        "ingest_user_message",
        "parse_llm_response",
        "process_slashcommand",
        "process_turn",
        "session_end",
    }
)

#: First-choice argument to show in a one-line call summary.  More specific
#: names win over the generic list.
_HINT_KEYS = {
    "ask_user": ("header", "question"),
    "call_assistant": ("name", "task"),
    "delegate_task": ("agentname", "prompt"),
    "await_subsession": ("sessionname",),
    "message_subsession": ("sessionname", "prompt"),
    "spawn_subtask": ("prompt",),
    "start_subsession": ("sessionname", "agentname"),
    "map": ("target",),
}
_DEFAULT_HINT_KEYS = (
    "path",
    "file_path",
    "pattern",
    "query",
    "command",
    "cmd",
    "url",
    "name",
    "sessionname",
    "agentname",
    "target",
    "prompt",
    "message",
    "task",
)

_ICONS = {
    "read": "▤",
    "list": "▤",
    "glob": "⌕",
    "grep": "⌕",
    "search": "⌕",
    "write": "✎",
    "edit": "✎",
    "multiedit": "✎",
    "append": "✎",
    "copy": "⧉",
    "shell": "▶",
    "bash": "▶",
    "execute": "▶",
    "python": "▶",
    "terminal": "▶",
    "browser": "◈",
    "delegate_task": "⇢",
    "spawn_subtask": "⇢",
    "start_subsession": "⇢",
    "message_subsession": "⇢",
    "await_subsession": "⇢",
    "call_assistant": "⇢",
    "ask_user": "?",
    "map": "⋔",
    "final_result": "✓",
    "load_skill": "✦",
}

_SHORT_STATUS = {
    "NEW": "new",
    "WAITING_QUEUE": "queued",
    "WAITING_RETRY": "retry",
    "WAITING_DEPENDENCY": "waiting",
    "WAITING_SUBTASKS_OR_HOOKS": "waiting",
    "WAITING_RATELIMIT": "rate-limited",
    "ACTIVE_QUEUED": "queued",
    "ACTIVE_RUNNING": "running",
    "HALTED_INPUT": "needs input",
    "HALTED_APPROVAL": "approval",
    "HALTED_STAGNATED": "step limit",
    "HALTED_PAUSED": "paused",
    "ENDED_SUCCESS": "done",
    "ENDED_FAILURE_EXCEPTION": "error",
    "ENDED_FAILURE_LOGIC": "failed",
    "ENDED_CANCELLED": "cancelled",
    "ENDED_STOPPED": "stopped",
}


# ---------------------------------------------------------------------------
# Call identity / classification
# ---------------------------------------------------------------------------


def task_definition(call: Any) -> Any:
    """Return the call's TaskDefinition without raising on partial objects."""
    definition = getattr(call, "task_definition", None)
    if definition is not None:
        return definition
    version = getattr(call, "task_definition_version", None)
    return getattr(version, "task_definition", None) if version else None


def task_version(call: Any) -> Any:
    version = getattr(call, "task_definition_version", None)
    if version is not None:
        return version
    definition = getattr(call, "task_definition", None)
    return getattr(definition, "latest_task_version", None) if definition else None


def call_name(call: Any) -> str:
    """Display name of an ``AgentTaskCall`` (never raises)."""
    try:
        definition = task_definition(call)
        if definition is not None and definition.name:
            return definition.name
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    pk = getattr(call, "pk", None)
    return f"call #{pk}" if pk is not None else "tool call"


def call_task_type(call: Any) -> str:
    try:
        return str(getattr(task_version(call), "task_type", "") or "")
    except Exception:  # pylint: disable=broad-exception-caught
        return ""


def call_group(call: Any) -> str:
    try:
        return str(getattr(task_definition(call), "group_name", "") or "")
    except Exception:  # pylint: disable=broad-exception-caught
        return ""


def is_framework_call(call: Any) -> bool:
    """True for one-step LLM plumbing (not a user-visible action)."""
    name = call_name(call)
    if name in FRAMEWORK_TASK_NAMES:
        return True
    task_type = call_task_type(call)
    if task_type in (TaskType.TOOL, TaskType.COMMAND):
        return False
    if call_group(call) == "core" and name not in VISIBLE_CORE_TASKS:
        return True
    return False


def call_kind(call: Any) -> str:
    if is_framework_call(call):
        return "framework"
    task_type = call_task_type(call)
    if task_type == TaskType.COMMAND:
        return "command"
    if task_type == TaskType.TOOL:
        return "tool"
    return "task"


def call_icon(call: Any) -> str:
    name = call_name(call)
    if name in _ICONS:
        return _ICONS[name]
    return {"command": "/", "tool": "⚙", "task": "◆", "framework": "·"}.get(
        call_kind(call), "⚙"
    )


def _collapse(text: Any, limit: int = 72) -> str:
    try:
        value = re.sub(r"\s+", " ", str(text)).strip()
    except Exception:  # pylint: disable=broad-exception-caught
        value = str(text)
    if len(value) > limit:
        return value[: limit - 1].rstrip() + "…"
    return value


@lru_cache(maxsize=256)
def _content_hint(pk: Any) -> str:
    """Short preview of a ``GenericContent`` payload (prompts, file text)."""
    try:
        text = GenericContent.objects.get(pk=pk).get()
    except Exception:  # pylint: disable=broad-exception-caught
        return ""
    return _collapse(text, 60)


def _ref_text(value: dict[str, Any]) -> str:
    type_name = value.get("_type") or "ref"
    pk = value.get("pk")
    if type_name == "GenericContent" and pk is not None:
        hint = _content_hint(pk)
        if hint:
            return hint
    return f"{type_name} #{pk}" if pk is not None else str(type_name)


def _hint_value(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, dict) and "_type" in value and "pk" in value:
        return _ref_text(value)
    if isinstance(value, str):
        return _collapse(value)
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, (list, tuple)):
        parts = [_hint_value(item) for item in value[:3]]
        text = ", ".join(part for part in parts if part)
        if len(value) > 3:
            text += f" (+{len(value) - 3})"
        return _collapse(text)
    if isinstance(value, dict):
        for key in ("path", "name", "pattern", "query", "command", "text", "content"):
            if key in value:
                return _hint_value(value[key])
        # An unrecognised dict is payload, not a summary.  Showing its raw
        # braces in a tool row is worse than showing no hint; the expanded
        # card renders the full structured payload.
        return ""
    return _collapse(value)


def call_hint(call: Any) -> str:
    """One short, human-readable argument hint for a call row."""
    args = getattr(call, "carguments_json", None)
    if not isinstance(args, dict):
        return _hint_value(args)
    name = call_name(call)
    keys = _HINT_KEYS.get(name, _DEFAULT_HINT_KEYS)
    for key in keys:
        if key in args:
            hint = _hint_value(args[key])
            if hint:
                return hint
    positional = args.get("*")
    if positional:
        hint = _hint_value(positional)
        if hint:
            return hint
    for key, value in args.items():
        if key in ("_type", "pk", "guardrail_reason"):
            continue
        hint = _hint_value(value)
        if hint:
            return hint
    return ""


# ---------------------------------------------------------------------------
# Status / timing
# ---------------------------------------------------------------------------


def status_class(call: Any) -> str:
    """Map a tool-call status to a card-status modifier."""
    detail = str(getattr(call, "status_detail", "") or "").upper()
    if "SUCCESS" in detail:
        return "success"
    if "FAILURE" in detail or "CANCELLED" in detail or "STOPPED" in detail:
        return "failure"
    status = str(getattr(call, "status", "") or "").lower()
    if status in ("success", "failure", "active", "waiting"):
        return status
    if status in ("halted", "ended"):
        return "waiting"
    return status or "waiting"


def status_text(call: Any) -> str:
    detail = str(getattr(call, "status_detail", "") or "").upper()
    if detail in _SHORT_STATUS:
        return _SHORT_STATUS[detail]
    status = str(getattr(call, "status", "") or "").lower()
    return {
        "new": "new",
        "waiting": "waiting",
        "active": "running",
        "halted": "paused",
        "ended": "done",
    }.get(status, status or "pending")


def status_label(call: Any) -> str:
    try:
        detail = str(getattr(call, "status_detail", "") or "")
        return str(dict(TaskCallStatusDetail.choices).get(detail, detail))
    except Exception:  # pylint: disable=broad-exception-caught
        return str(getattr(call, "status", "") or "")


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return ""
    try:
        seconds = max(float(seconds), 0)
    except (TypeError, ValueError):
        return ""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m {int(seconds % 60):02d}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60:02d}m"


def call_duration(call: Any) -> str:
    try:
        start = getattr(call, "created_at", None)
        end = getattr(call, "ended_at", None) or getattr(call, "updated_at", None)
        if start is None or end is None:
            return ""
        return fmt_duration((end - start).total_seconds())
    except Exception:  # pylint: disable=broad-exception-caught
        return ""


def clock(value: Any) -> str:
    if value is None:
        return ""
    try:
        return timezone.localtime(value).strftime("%H:%M")
    except Exception:  # pylint: disable=broad-exception-caught
        return ""


def is_active(call: Any) -> bool:
    return str(getattr(call, "status", "") or "") != str(TaskCallStatus.ENDED)


def is_approval(call: Any) -> bool:
    return str(getattr(call, "status_detail", "") or "") == str(
        TaskCallStatusDetail.HALTED_APPROVAL
    )


# ---------------------------------------------------------------------------
# Sessions / subsessions
# ---------------------------------------------------------------------------


def session_info(session: Any) -> dict[str, Any] | None:
    if session is None:
        return None
    version = getattr(session, "latest_session_version", None)
    agent = getattr(version, "agent", None) if version is not None else None
    try:
        type_label = session.get_session_type_display()
    except Exception:  # pylint: disable=broad-exception-caught
        type_label = str(getattr(session, "session_type", "") or "")
    pk = getattr(session, "pk", None)
    return {
        "pk": pk,
        "name": getattr(session, "name", "") or f"Session #{pk}",
        "agent_name": getattr(agent, "name", "") or "",
        "type": type_label,
        "is_active": bool(getattr(session, "is_active", False)),
        "href": reverse("webui:chat", args=[pk]) if pk is not None else "",
    }


def _subsession_entry(call: Any) -> dict[str, Any] | None:
    session = getattr(call, "session", None)
    info = session_info(session)
    if info is None:
        return None
    return {
        "session": info,
        "root_call": call,
        "name": info["name"],
        "agent_name": info["agent_name"],
        "status_text": status_text(call),
        "status_class": status_class(call),
        "duration": call_duration(call),
        "started": clock(getattr(call, "created_at", None)),
        "href": info["href"],
        "call_href": reverse("webui:call_detail", args=[call.pk]),
    }


def _subsession_from_session(session: Any) -> dict[str, Any] | None:
    info = session_info(session)
    if info is None:
        return None
    return {
        "session": info,
        "root_call": None,
        "name": info["name"],
        "status_text": "active" if info["is_active"] else "idle",
        "status_class": "active" if info["is_active"] else "waiting",
        "duration": "",
        "started": "",
        "href": info["href"],
        "call_href": "",
    }


def _payload_session_pks(value: Any, found: set[int]) -> None:
    """Collect ``session_pk`` hints from a result payload (start_subsession)."""
    if isinstance(value, dict):
        pk = value.get("session_pk")
        if isinstance(pk, int):
            found.add(pk)
        for item in value.values():
            _payload_session_pks(item, found)
    elif isinstance(value, list):
        for item in value:
            _payload_session_pks(item, found)


# ---------------------------------------------------------------------------
# Payload rendering (input / output)
# ---------------------------------------------------------------------------


def _is_ref(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and len(value) == 2
        and "_type" in value
        and "pk" in value
    )


def _ref_object(type_name: str, pk: Any, cache: dict[tuple[str, Any], Any]) -> Any:
    key = (type_name, pk)
    if key in cache:
        return cache[key]
    obj = None
    if type_name not in ("AgentTaskCall", "AgentTaskRun", "GenericContent"):
        cache[key] = None
        return None
    try:
        model = apps.get_model("server", type_name)
        queryset = model.objects.all()
        if type_name == "AgentTaskCall":
            queryset = queryset.select_related(
                "task_definition",
                "task_definition_version__task_definition",
                "session__latest_session_version__agent",
            )
        elif type_name == "AgentTaskRun":
            queryset = queryset.select_related(
                "agent_task_call__task_definition",
                "agent_task_call__session__latest_session_version__agent",
            )
        obj = queryset.get(pk=pk)
    except Exception:  # pylint: disable=broad-exception-caught
        obj = None
    cache[key] = obj
    return obj


def _ref_payload(
    value: dict[str, Any],
    cache: dict[tuple[str, Any], Any],
    max_text: int,
) -> dict[str, Any]:
    type_name = str(value.get("_type") or "ref")
    pk = value.get("pk")
    obj = _ref_object(type_name, pk, cache)
    if isinstance(obj, GenericContent):
        try:
            text = obj.get()
        except Exception:  # pylint: disable=broad-exception-caught
            text = ""
        return _display_text_node(text, max_text)
    if isinstance(obj, AgentTaskCall):
        return {
            "kind": "ref",
            "type": type_name,
            "pk": obj.pk,
            "name": call_name(obj),
            "hint": call_hint(obj),
            "status_text": status_text(obj),
            "status_class": status_class(obj),
            "icon": call_icon(obj),
            "session": session_info(getattr(obj, "session", None))
            if getattr(obj, "session_id", None)
            else None,
            "href": reverse("webui:call_detail", args=[obj.pk]),
        }
    if isinstance(obj, AgentTaskRun):
        call = getattr(obj, "agent_task_call", None)
        return {
            "kind": "ref",
            "type": type_name,
            "pk": obj.pk,
            "name": f"run #{obj.pk}" + (f" · {call_name(call)}" if call else ""),
            "hint": "",
            "status_text": str(getattr(obj, "status", "") or "").lower(),
            "status_class": "active"
            if str(getattr(obj, "status", "")) in ("ACTIVE", "QUEUED", "WAITING_RESULTTASKS")
            else ("success" if str(getattr(obj, "status", "")) == "SUCCESS" else "failure"),
            "icon": "·",
            "session": session_info(getattr(call, "session", None)) if call else None,
            "href": reverse("webui:call_detail", args=[call.pk]) if call else "",
        }
    return {
        "kind": "ref",
        "type": type_name,
        "pk": pk,
        "name": f"{type_name} #{pk}",
        "hint": "",
        "status_text": "",
        "status_class": "waiting",
        "icon": "·",
        "session": None,
        "href": "",
    }


def _display_text_node(text: Any, max_text: int, kind: str = "text") -> dict[str, Any]:
    """Build a text/JSON node, recording whether the display slice was cut."""
    value = str(text)
    node: dict[str, Any] = {"kind": kind, "text": value[:max_text]}
    if len(value) > max_text:
        node.update(
            truncated=True,
            shown_chars=len(node["text"]),
            total_chars=len(value),
        )
    return node


def build_payload(
    value: Any,
    *,
    cache: dict[tuple[str, Any], Any] | None = None,
    max_text: int = 4000,
    depth: int = 0,
) -> dict[str, Any]:
    """Turn arbitrary result/argument data into a small template tree.

    Model references stay references (instead of being resolved into nested
    result payloads) so a returned ``AgentTaskCall`` reads as a linkable task
    chip rather than a wall of JSON.
    """
    cache = cache if cache is not None else {}
    if isinstance(value, AgentTaskCall):
        return _ref_payload(
            {"_type": "AgentTaskCall", "pk": value.pk}, cache, max_text
        )
    if isinstance(value, AgentTaskRun):
        return _ref_payload({"_type": "AgentTaskRun", "pk": value.pk}, cache, max_text)
    if isinstance(value, GenericContent):
        try:
            text = value.get()
        except Exception:  # pylint: disable=broad-exception-caught
            text = ""
        return _display_text_node(text, max_text)
    if _is_ref(value):
        return _ref_payload(value, cache, max_text)
    if isinstance(value, dict):
        if not value:
            return {"kind": "empty", "text": "{}"}
        if depth >= 5:
            return _display_text_node(_json(value), max_text, "json")
        return {
            "kind": "dict",
            "rows": [
                {
                    "key": str(key),
                    "value": build_payload(
                        item, cache=cache, max_text=max_text, depth=depth + 1
                    ),
                }
                for key, item in value.items()
            ],
        }
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if not items:
            return {"kind": "empty", "text": "[]"}
        if depth >= 5:
            return _display_text_node(_json(items), max_text, "json")
        return {
            "kind": "list",
            "items": [
                build_payload(item, cache=cache, max_text=max_text, depth=depth + 1)
                for item in items
            ],
        }
    if isinstance(value, str):
        return _display_text_node(value, max_text)
    if value is None:
        return {"kind": "empty", "text": "null"}
    return {"kind": "scalar", "text": str(value)}


def _json(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _refs_in(value: Any, found: list[dict[str, Any]], seen: set[tuple[str, Any]]) -> None:
    if isinstance(value, AgentTaskCall):
        value = {"_type": "AgentTaskCall", "pk": value.pk}
    elif isinstance(value, AgentTaskRun):
        value = {"_type": "AgentTaskRun", "pk": value.pk}
    if _is_ref(value):
        key = (str(value.get("_type")), value.get("pk"))
        if key not in seen:
            seen.add(key)
            found.append(value)
        return
    if isinstance(value, dict):
        for item in value.values():
            _refs_in(item, found, seen)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _refs_in(item, found, seen)


def payload_refs(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    _refs_in(value, found, set())
    return found


# ---------------------------------------------------------------------------
# Reference sections (call detail)
# ---------------------------------------------------------------------------


def _call_ref(call: Any) -> dict[str, Any]:
    return {
        "call": call,
        "pk": call.pk,
        "name": call_name(call),
        "kind": call_kind(call),
        "icon": call_icon(call),
        "hint": call_hint(call),
        "status_text": status_text(call),
        "status_class": status_class(call),
        "duration": call_duration(call),
        "session": session_info(getattr(call, "session", None))
        if getattr(call, "session_id", None)
        else None,
        "href": reverse("webui:call_detail", args=[call.pk]),
    }


def _result_run(call: Any) -> Any:
    run = getattr(call, "taskcall_result_run", None)
    if run is not None:
        return run
    run_id = getattr(call, "taskcall_result_run_id", None)
    if not run_id:
        return None
    try:
        return AgentTaskRun.objects.select_related(
            "agent_task_call__task_definition"
        ).get(pk=run_id)
    except AgentTaskRun.DoesNotExist:
        return None


def returned_calls(call: Any) -> list[Any]:
    """Calls returned in this call's result and awaited by the run."""
    run = _result_run(call)
    if run is None:
        return []
    try:
        return list(
            run.taskrun_result_references.select_related(
                "task_definition",
                "task_definition_version__task_definition",
                "session__latest_session_version__agent",
            ).order_by("pk")
        )
    except Exception:  # pylint: disable=broad-exception-caught
        return []


def dependency_calls(call: Any) -> list[Any]:
    """Calls whose results this call needed as arguments."""
    try:
        return list(
            call.taskcall_arg_references.select_related(
                "task_definition",
                "task_definition_version__task_definition",
                "session__latest_session_version__agent",
            ).order_by("pk")
        )
    except Exception:  # pylint: disable=broad-exception-caught
        return []


def launched_calls(call: Any) -> list[Any]:
    """Direct children created while this call's run was executing."""
    try:
        return list(
            AgentTaskCall.objects.filter(
                parent_taskrun__agent_task_call_id=call.pk
            )
            .select_related(
                "task_definition",
                "task_definition_version__task_definition",
                "session__latest_session_version__agent",
            )
            .order_by("created_at", "pk")
        )
    except Exception:  # pylint: disable=broad-exception-caught
        return []


def build_call_references(call: Any) -> dict[str, Any]:
    """The three edges around one call, split for the detail template."""
    own_session_id = getattr(call, "session_id", None)
    returned = returned_calls(call)
    depends = dependency_calls(call)
    launched = launched_calls(call)

    returned_pks = {item.pk for item in returned}
    launched_only = [item for item in launched if item.pk not in returned_pks]

    subsessions: dict[int, dict[str, Any]] = {}
    for item in [*returned, *launched]:
        session = getattr(item, "session", None)
        session_id = getattr(item, "session_id", None)
        if session is None or session_id in (None, own_session_id):
            continue
        if session_id not in subsessions:
            entry = _subsession_entry(item)
            if entry is not None:
                subsessions[session_id] = entry

    # ``start_subsession`` returns only a session_pk, not a call.
    result_json = getattr(call, "result_json", None)
    session_pks: set[int] = set()
    _payload_session_pks(result_json, session_pks)
    missing = [pk for pk in session_pks if pk not in subsessions]
    if missing:
        from server.models.sessions.session import SessionModel

        for session in SessionModel.objects.select_related(
            "latest_session_version__agent"
        ).filter(pk__in=missing):
            entry = _subsession_from_session(session)
            if entry is not None:
                subsessions[session.pk] = entry

    return {
        "depends_on": [_call_ref(item) for item in depends],
        "returned": [_call_ref(item) for item in returned],
        "launched": [_call_ref(item) for item in launched_only],
        "subsessions": list(subsessions.values()),
    }


# ---------------------------------------------------------------------------
# Chat tool-card sub-flow
# ---------------------------------------------------------------------------


def _calls_by_pk(pks: Iterable[int]) -> dict[int, Any]:
    pks = [pk for pk in pks if pk]
    if not pks:
        return {}
    rows = AgentTaskCall.objects.filter(pk__in=pks).select_related(
        "task_definition",
        "task_definition_version__task_definition",
        "session__latest_session_version__agent",
        "parent_taskrun",
    )
    return {call.pk: call for call in rows}


def _created_key(call: Any) -> tuple[bool, Any, int]:
    created = getattr(call, "created_at", None)
    return (created is None, created, int(getattr(call, "pk", 0) or 0))


def _prefix(ancestor_last: list[bool], is_last: bool) -> str:
    prefix = "".join("   " if last else "│  " for last in ancestor_last)
    return prefix + ("└─ " if is_last else "├─ ")


def _flow_row(
    call: Any,
    depth: int,
    ancestor_last: list[bool],
    is_last: bool,
    *,
    returned: bool = False,
    executing: bool = False,
) -> dict[str, Any]:
    return {
        "kind": "call",
        "pk": call.pk,
        "call": call,
        "depth": depth,
        "prefix": _prefix(ancestor_last, is_last),
        "name": call_name(call),
        "icon": "↩" if returned else call_icon(call),
        "call_kind": call_kind(call),
        "hint": call_hint(call),
        "returned": returned,
        "status": str(getattr(call, "status", "") or ""),
        "status_detail": str(getattr(call, "status_detail", "") or ""),
        "status_class": status_class(call),
        "status_text": status_text(call),
        "started": clock(getattr(call, "created_at", None)),
        "duration": call_duration(call),
        "executing": executing,
        "session": session_info(getattr(call, "session", None))
        if getattr(call, "session_id", None)
        else None,
        "href": reverse("webui:call_detail", args=[call.pk]),
    }


def _subsession_flow_row(
    call: Any,
    depth: int,
    ancestor_last: list[bool],
    is_last: bool,
) -> dict[str, Any]:
    info = session_info(getattr(call, "session", None))
    agent = (info or {}).get("agent_name") or ""
    return {
        "kind": "subsession",
        "pk": None,
        "call": call,
        "depth": depth,
        "prefix": _prefix(ancestor_last, is_last),
        "name": (info or {}).get("name") or f"Session #{getattr(call, 'session_id', '?')}",
        "icon": "⇢",
        "call_kind": "subsession",
        "hint": " · ".join(part for part in (agent, (info or {}).get("type", "")) if part),
        "returned": False,
        "status": str(getattr(call, "status", "") or ""),
        "status_detail": str(getattr(call, "status_detail", "") or ""),
        "status_class": status_class(call),
        "status_text": status_text(call),
        "started": clock(getattr(call, "created_at", None)),
        "duration": call_duration(call),
        "executing": False,
        "session": info,
        "href": (info or {}).get("href", ""),
        "call_href": reverse("webui:call_detail", args=[call.pk]),
    }


def build_subcall_flow(
    call: Any,
    *,
    full: bool = False,
    max_depth: int = 6,
    max_nodes: int = 400,
    max_rows: int = 300,
) -> dict[str, Any]:
    """Rows for the live sub-task flow inside a chat tool card.

    The flow is chronological and depth-first, but it deliberately stops at a
    session boundary: a delegated child session becomes one *subsession* row
    that links to the child chat instead of dumping that session's internal
    ``process_turn`` pipeline into the parent card.  Framework plumbing in the
    same session is counted and hidden unless *full* is set.
    """
    graph, children = _fetch_graph([call], max_depth=max_depth, max_nodes=max_nodes)
    returned = _returned_map(graph.values())

    extra = {
        ref.pk
        for refs in returned.values()
        for ref in refs
        if ref.pk not in graph and ref.pk != getattr(call, "pk", None)
    }
    if extra:
        graph.update(_calls_by_pk(extra))

    rows: list[dict[str, Any]] = []
    hidden_framework = 0
    flow_truncated = False
    seen: set[int] = {getattr(call, "pk", None)}
    seen_sessions: set[int] = set()

    def child_items(parent: Any) -> list[tuple[str, Any]]:
        items: list[tuple[str, Any]] = [
            ("child", child) for child in children.get(parent.pk, [])
        ]
        items.extend(
            ("returned", ref)
            for ref in returned.get(parent.pk, [])
            if ref.pk != parent.pk
        )
        items.sort(key=lambda item: _created_key(item[1]))
        return items

    def walk(parent: Any, ancestor_last: list[bool]) -> None:
        nonlocal hidden_framework, flow_truncated
        if len(rows) >= max_rows:
            flow_truncated = True
            return
        items = [
            (kind, item) for kind, item in child_items(parent) if item.pk not in seen
        ]
        # Hide one-step framework plumbing but keep its meaningful descendants
        # by promoting them to the parent's level.
        expanded: list[tuple[str, Any]] = []
        for kind, item in items:
            if (
                item.session_id == parent.session_id
                and is_framework_call(item)
                and not full
            ):
                hidden_framework += 1
                seen.add(item.pk)
                for sub_kind, sub in child_items(item):
                    if sub.pk not in seen:
                        expanded.append((sub_kind, sub))
            else:
                expanded.append((kind, item))
        expanded.sort(key=lambda item: _created_key(item[1]))

        for index, (kind, item) in enumerate(expanded):
            if item.pk in seen:
                continue
            is_last = index == len(expanded) - 1
            if item.session_id != parent.session_id:
                if item.session_id in seen_sessions:
                    seen.add(item.pk)
                    continue
                seen_sessions.add(item.session_id)
                seen.add(item.pk)
                rows.append(
                    _subsession_flow_row(
                        item, len(ancestor_last) + 1, ancestor_last, is_last
                    )
                )
                continue
            seen.add(item.pk)
            rows.append(
                _flow_row(
                    item,
                    len(ancestor_last) + 1,
                    ancestor_last,
                    is_last,
                    returned=kind == "returned",
                )
            )
            walk(item, ancestor_last + [is_last])

    walk(call, [])

    # A truncated/oldest-first walk can miss a call that is executing right
    # now.  Pin those so a live card never looks idle while work is happening.
    running: list[dict[str, Any]] = []
    included = {row["pk"] for row in rows if row["kind"] == "call"}
    try:
        pins = call.get_executing_subcalls() or []
    except Exception:  # pylint: disable=broad-exception-caught
        pins = []
    for pin in pins:
        pinned = pin.get("call")
        if pinned is None or pinned.pk in included:
            continue
        included.add(pinned.pk)
        node = _flow_row(pinned, 1, [], True, executing=True)
        node["prefix"] = ""
        running.append(node)

    counts = subcall_counts(call)
    counts["hidden_framework"] = hidden_framework
    counts["truncated"] = bool(counts.get("truncated") or flow_truncated)
    return {
        "call": call,
        "nodes": rows,
        "running": running,
        "counts": counts,
        "full": bool(full),
        "has_content": bool(
            rows or running or counts.get("finished") or counts.get("active")
        ),
    }


def subcall_counts(call: Any) -> dict[str, Any]:
    """Cheap descendant counts for the collapsed tool card."""
    try:
        counts = call.count_subcalls(max_depth=6, max_nodes=500) or {}
    except Exception:  # pylint: disable=broad-exception-caught
        counts = {}
    active = int(counts.get("active", 0) or 0)
    finished = int(counts.get("finished", 0) or 0)
    executing = len(counts.get("executing") or [])
    return {
        "active": active,
        "finished": finished,
        "executing": executing,
        "waiting": max(active - executing, 0),
        "truncated": bool(counts.get("truncated", False)),
    }


# ---------------------------------------------------------------------------
# Right-bar Calls panel
# ---------------------------------------------------------------------------


def _visible_calls(session: Any, limit: int) -> list[Any]:
    """User-facing calls linked to chat messages, newest window first."""
    parts = (
        MessagePart.objects.filter(
            message__session=session,
            type=MessagePartType.TOOLCALL,
            tool_call__isnull=False,
        )
        .select_related(
            "tool_call__task_definition",
            "tool_call__task_definition_version__task_definition",
            "tool_call__session__latest_session_version__agent",
        )
        .order_by("-message__pk", "-pk")[: max(limit * 2, limit)]
    )
    calls: list[Any] = []
    seen: set[int] = set()
    for part in parts:
        call = part.tool_call
        if call is None or call.pk in seen:
            continue
        seen.add(call.pk)
        calls.append(call)
        if len(calls) >= limit:
            break
    calls.reverse()
    return calls


def _fetch_graph(
    roots: Iterable[Any], *, max_depth: int = 5, max_nodes: int = 500
) -> tuple[dict[int, Any], dict[int, list[Any]]]:
    """Fetch descendants in a few batched BFS queries.

    Stops at session boundaries: a delegated child session is a destination,
    not another indentation level in the parent's framework pipeline.
    """
    graph: dict[int, Any] = {call.pk: call for call in roots}
    children: dict[int, list[Any]] = defaultdict(list)
    frontier = set(graph)
    fetched = 0
    for _ in range(max_depth):
        remaining = max_nodes - fetched
        if not frontier or remaining <= 0:
            break
        rows = list(
            AgentTaskCall.objects.filter(
                parent_taskrun__agent_task_call_id__in=frontier
            )
            .select_related(
                "task_definition",
                "task_definition_version__task_definition",
                "session__latest_session_version__agent",
                "parent_taskrun",
            )
            .order_by("created_at", "pk")[:remaining]
        )
        next_frontier: set[int] = set()
        for call in rows:
            if call.pk in graph:
                continue
            parent_run = getattr(call, "parent_taskrun", None)
            parent_pk = getattr(parent_run, "agent_task_call_id", None)
            graph[call.pk] = call
            children[parent_pk].append(call)
            fetched += 1
            parent = graph.get(parent_pk)
            if parent is not None and call.session_id != parent.session_id:
                continue
            next_frontier.add(call.pk)
        frontier = next_frontier
    return graph, children


def _returned_map(calls: Iterable[Any]) -> dict[int, list[Any]]:
    calls = list(calls)
    run_ids = {
        call.taskcall_result_run_id
        for call in calls
        if getattr(call, "taskcall_result_run_id", None)
    }
    if not run_ids:
        return {}
    runs = AgentTaskRun.objects.filter(pk__in=run_ids).prefetch_related(
        Prefetch(
            "taskrun_result_references",
            queryset=AgentTaskCall.objects.select_related(
                "task_definition",
                "task_definition_version__task_definition",
                "session__latest_session_version__agent",
            ).order_by("pk"),
        )
    )
    by_run = {run.pk: list(run.taskrun_result_references.all()) for run in runs}
    return {
        call.pk: by_run.get(call.taskcall_result_run_id, []) for call in calls
    }


def _arg_counts(pks: Iterable[int]) -> dict[int, int]:
    pks = list(pks)
    if not pks:
        return {}
    return dict(
        AgentTaskCall.objects.filter(pk__in=pks)
        .annotate(n=Count("taskcall_arg_references"))
        .values_list("pk", "n")
    )


def _row(call: Any, depth: int, *, returned: bool = False) -> dict[str, Any]:
    return {
        "kind": "call",
        "call": call,
        "pk": call.pk,
        "depth": depth,
        "name": call_name(call),
        "icon": call_icon(call),
        "call_kind": call_kind(call),
        "hint": call_hint(call),
        "status_text": status_text(call),
        "status_class": status_class(call),
        "status_detail": str(getattr(call, "status_detail", "") or ""),
        "duration": call_duration(call),
        "started": clock(getattr(call, "created_at", None)),
        "active": is_active(call),
        "approval": is_approval(call),
        "returned": returned,
        "session": session_info(getattr(call, "session", None))
        if getattr(call, "session_id", None)
        else None,
        "href": reverse("webui:call_detail", args=[call.pk]),
    }


def _subsession_row(entry: dict[str, Any], depth: int) -> dict[str, Any]:
    return {
        "kind": "subsession",
        "call": entry.get("root_call"),
        "pk": None,
        "depth": depth,
        "name": entry["name"],
        "icon": "⇢",
        "call_kind": "subsession",
        "hint": entry["session"].get("agent_name", ""),
        "status_text": entry["status_text"],
        "status_class": entry["status_class"],
        "status_detail": "",
        "duration": entry["duration"],
        "started": entry["started"],
        "active": entry["status_class"] == "active",
        "approval": False,
        "returned": False,
        "session": entry["session"],
        "href": entry["href"],
        "call_href": entry.get("call_href", ""),
    }


def build_calls_panel(
    session: Any,
    *,
    show_framework: bool = False,
    limit: int = 25,
    max_rows: int = 200,
) -> dict[str, Any]:
    """Build the right-bar Calls panel.

    Default view = user-facing calls grouped by time, with their meaningful
    descendants.  Framework plumbing is counted and hidden behind a toggle;
    cross-session children become a single subsession row with a link to the
    child chat.
    """
    visible = _visible_calls(session, limit)
    if not visible:
        # A framework-only/cron session still deserves an activity view.
        visible = list(
            AgentTaskCall.objects.filter(session=session)
            .select_related(
                "task_definition",
                "task_definition_version__task_definition",
                "session__latest_session_version__agent",
            )
            .order_by("-pk")[:limit]
        )
        visible.reverse()
    if not visible:
        return {
            "call_rows": [],
            "running_rows": [],
            "call_groups": [],
            "call_counts": {"active": 0, "finished": 0, "failed": 0, "approval": 0},
            "hidden_framework": 0,
            "show_framework": show_framework,
            "truncated": False,
        }

    graph, children = _fetch_graph(
        visible, max_depth=5, max_nodes=min(max_rows * 2, 1200)
    )
    returned_by_call = _returned_map(graph.values())
    arg_counts = _arg_counts(graph.keys())

    # Result references can point outside the parent_taskrun subtree (e.g.
    # ``await_subsession`` returns an existing call).  Make sure they are
    # available to the walk.
    extra_pks: set[int] = set()
    for refs in returned_by_call.values():
        for ref in refs:
            if ref.pk not in graph:
                extra_pks.add(ref.pk)
    if extra_pks:
        for call in AgentTaskCall.objects.filter(pk__in=extra_pks).select_related(
            "task_definition",
            "task_definition_version__task_definition",
            "session__latest_session_version__agent",
        ):
            graph[call.pk] = call

    rows: list[dict[str, Any]] = []
    seen_calls: set[int] = set()
    seen_sessions: set[int] = set()
    hidden_framework = 0
    truncated = False

    def at_cap() -> bool:
        nonlocal truncated
        if len(rows) >= max_rows:
            truncated = True
            return True
        return False

    def add_subsession(call: Any, depth: int) -> None:
        session_id = getattr(call, "session_id", None)
        if session_id in seen_sessions or at_cap():
            return
        seen_sessions.add(session_id)
        entry = _subsession_entry(call)
        if entry is not None:
            rows.append(_subsession_row(entry, depth))

    def walk(call: Any, depth: int, *, returned: bool = False) -> None:
        nonlocal hidden_framework
        if call.pk in seen_calls or at_cap():
            return
        if is_framework_call(call) and not show_framework:
            seen_calls.add(call.pk)
            hidden_framework += 1
            # Keep meaningful descendants reachable by promoting them.
            for child in children.get(call.pk, []):
                if child.session_id != call.session_id:
                    add_subsession(child, depth)
                else:
                    walk(child, depth)
            for ref in returned_by_call.get(call.pk, []):
                if ref.session_id != call.session_id:
                    add_subsession(ref, depth)
                else:
                    walk(ref, depth, returned=True)
            return
        seen_calls.add(call.pk)
        row = _row(call, depth, returned=returned)
        row["depends_count"] = arg_counts.get(call.pk, 0)
        rows.append(row)
        for child in children.get(call.pk, []):
            if child.session_id != call.session_id:
                add_subsession(child, depth + 1)
            else:
                walk(child, depth + 1)
        for ref in returned_by_call.get(call.pk, []):
            if ref.session_id != call.session_id:
                add_subsession(ref, depth + 1)
            else:
                walk(ref, depth + 1, returned=True)

    for call in visible:
        if getattr(call, "session_id", None) != session.pk:
            add_subsession(call, 0)
        else:
            walk(call, 0)

    call_rows = [row for row in rows if row["kind"] == "call"]
    running_rows = [row for row in rows if row["active"]]
    finished = sum(1 for row in call_rows if not row["active"])
    failed = sum(
        1
        for row in call_rows
        if row["status_class"] == "failure" and not row["active"]
    )
    approval = sum(1 for row in call_rows if row["approval"])

    groups: list[dict[str, Any]] = []
    by_day: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        if row["active"]:
            continue
        call = row.get("call")
        created = getattr(call, "created_at", None) if call is not None else None
        day = timezone.localtime(created).date() if created else None
        by_day.setdefault(day, []).append(row)
    today = timezone.localdate()
    for day in sorted(by_day, key=lambda item: (item is None, item), reverse=True):
        if day == today:
            label = "Today"
        elif day == today - timezone.timedelta(days=1):
            label = "Yesterday"
        elif day is None:
            label = "Undated"
        else:
            label = day.strftime("%b %d, %Y")
        groups.append({"label": label, "rows": by_day[day]})

    return {
        "call_rows": rows,
        "running_rows": running_rows,
        "call_groups": groups,
        "call_counts": {
            "active": len(running_rows),
            "finished": finished,
            "failed": failed,
            "approval": approval,
        },
        "hidden_framework": hidden_framework,
        "show_framework": show_framework,
        "truncated": truncated,
        # Every visible call key already covers its descendants: the model
        # publishes ancestor call keys for cross-session child writes.
        "call_watch_pks": [call.pk for call in visible],
    }
