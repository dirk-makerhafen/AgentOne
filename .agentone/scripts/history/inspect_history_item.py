"""Inspect one history item in full (drill-down for search hits).

List/search tools return ~500-char previews. This is the only history tool
that returns large payloads — and only for a single message or tool call at
a time. Scope-checked: the item must belong to your own session (or to a
transitive child subsession when reached via an ``include_subsessions``
search).
"""

from __future__ import annotations

import json
from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessagePartType
from server.models.enums.task_enums import TaskCallStatusDetail
from server.models.message import Message
from server.models.tasks.agent_task_call import AgentTaskCall

MAX_CHARS = 8000
ENDED_DETAILS = {
    TaskCallStatusDetail.ENDED_SUCCESS,
    TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION,
    TaskCallStatusDetail.ENDED_FAILURE_LOGIC,
    TaskCallStatusDetail.ENDED_CANCELLED,
    TaskCallStatusDetail.ENDED_STOPPED,
}


def _str(value: Any) -> str:
    return str(getattr(value, "value", value))


def _full(raw: Any, max_chars: int) -> tuple[str, bool]:
    try:
        text = raw if isinstance(raw, str) else json.dumps(raw, default=str, ensure_ascii=False) if raw is not None else ""
    except Exception:
        text = ""
    if len(text) > max_chars:
        return text[:max_chars] + "…[truncated]", True
    return text, False


def _descendant_ids(session: Session) -> set[int]:
    from server.models.sessions.session import SessionModel

    seen = {session.model.pk}
    frontier = [session.model.pk]
    while frontier:
        children = list(
            SessionModel.objects.filter(parent_session_id__in=frontier).values_list("pk", flat=True)
        )
        new = [pk for pk in children if pk not in seen]
        if not new:
            break
        seen.update(new)
        frontier = new
    return seen


def _message_dict(msg: Message, max_chars: int) -> dict[str, Any]:
    parts = []
    for part in msg.parts.all().select_related("tool_call__task_definition", "content", "template_data"):
        try:
            rendered = part.to_string()
        except Exception as exc:
            rendered = f"[unrenderable part: {exc}]"
        body, truncated = _full(rendered, max_chars)
        entry: dict[str, Any] = {
            "part_pk": part.pk,
            "type": _str(part.type),
            "content_type": _str(part.content_type),
            "tokens": part.tokens,
            "body": body,
            "truncated": truncated,
            "is_compaction_boundary": part.type == MessagePartType.COMPACTION,
        }
        if part.tool_call_id:
            tc = part.tool_call
            entry["tool_call_pk"] = tc.pk
            try:
                entry["tool_call_name"] = tc.task_definition.name
            except Exception:
                entry["tool_call_name"] = ""
            entry["tool_call_status"] = _str(tc.status)
            entry["tool_call_status_detail"] = _str(tc.status_detail)
        parts.append(entry)
    return {
        "message_pk": msg.pk,
        "session_pk": msg.session_id,
        "role": _str(msg.role),
        "source": _str(msg.source),
        "created_at": msg.created_at.isoformat() if msg.created_at else "",
        "hidden_from_llm": bool(msg.hide_from_context or _str(msg.role) == "info"),
        "parts": parts,
    }


def _tool_call_dict(tc: AgentTaskCall, max_chars: int) -> dict[str, Any]:
    try:
        name = tc.task_definition.name
    except Exception:
        name = ""
    try:
        args_preview, args_truncated = _full(tc.carguments_json, max_chars)
    except Exception:
        args_preview, args_truncated = "[unreadable arguments]", False
    out: dict[str, Any] = {
        "task_call_pk": tc.pk,
        "session_pk": tc.session_id,
        "task_name": name,
        "status": _str(tc.status),
        "status_detail": _str(tc.status_detail),
        "created_at": tc.created_at.isoformat() if tc.created_at else "",
        "ended_at": tc.ended_at.isoformat() if tc.ended_at else "",
        "arguments_preview": args_preview,
        "arguments_truncated": args_truncated,
    }
    run = tc.taskcall_result_run
    if run is not None:
        out["result_run_pk"] = run.pk
        out["result_run_status"] = _str(run.status)
        try:
            result_preview, result_truncated = _full(run.result_json, max_chars)
        except Exception:
            result_preview, result_truncated = "[unreadable result]", False
        out["result_preview"] = result_preview
        out["result_truncated"] = result_truncated
    elif tc.status_detail not in ENDED_DETAILS:
        out["result_preview"] = "[call has not ended yet — no result available]"
        out["result_truncated"] = False
    return out


def inspect_history_item(
    _session: Session,
    message_pk: int | None = None,
    task_call_pk: int | None = None,
    max_chars: int = MAX_CHARS,
) -> dict[str, Any]:
    """Return the full content of one message or tool call.

    Args:
        message_pk: Inspect this message (all parts, full bodies).
        task_call_pk: Inspect this tool/task call instead (arguments +
            result preview, without blocking on unfinished calls).
        max_chars: Per-body char cap (default 8000, hard cap 8000).

    Returns:
        ``{"type": "message"|"tool_call", ...}`` on success,
        ``{"error": ...}`` when the pk is missing, unknown, or outside
        your session scope (own session + transitive subsessions).
    """
    try:
        if (message_pk is None) == (task_call_pk is None):
            return {"error": "Pass exactly one of message_pk or task_call_pk."}
        max_chars = max(1, min(int(max_chars), MAX_CHARS))
        scope = _descendant_ids(_session)

        if message_pk is not None:
            try:
                msg = Message.objects.get(pk=int(message_pk))
            except (Message.DoesNotExist, ValueError):
                return {"error": f"Message {message_pk} not found."}
            if msg.session_id not in scope:
                return {"error": f"Message {message_pk} is outside your session scope."}
            out = _message_dict(msg, max_chars)
            out["type"] = "message"
            return out

        try:
            tc = AgentTaskCall.objects.select_related("task_definition").get(pk=int(task_call_pk))
        except (AgentTaskCall.DoesNotExist, ValueError):
            return {"error": f"Tool call {task_call_pk} not found."}
        if tc.session_id not in scope:
            return {"error": f"Tool call {task_call_pk} is outside your session scope."}
        out = _tool_call_dict(tc, max_chars)
        out["type"] = "tool_call"
        return out
    except Exception as exc:
        return {"error": f"inspect_history_item failed: {exc}"}
