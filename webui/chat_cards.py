"""Status cards shown under the chat thread.

The legacy UI rendered these as separate pyHtmlGui views pinned above the
composer.  The server-rendered equivalent is one context dict built with the
thread fragment, so every SSE refresh re-reads the current call state:

* ``queue``        — user messages parked at ``WAITING_QUEUE``
* ``questions``    — ``ask_user`` calls halted for answers
* ``approvals``    — every other call halted for approval (guardrails/tools)
* ``turn_limit``   — the session hit its unattended-turn ceiling
* ``ratelimit``    — calls parked at ``WAITING_RATELIMIT``

Keeping this a pure read keeps the cards stateless: the browser only posts an
action and the returned thread fragment re-renders the new state.
"""

from __future__ import annotations

import json
from typing import Any

from django.utils import timezone

from runtime.user_questions import ASK_USER_TOOL_NAME, normalize_questions
from server.models.content import resolve_generic_content_refs
from server.models.enums.task_enums import TaskCallStatusDetail
from server.models.tasks.agent_task_call import AgentTaskCall

#: How many pending calls a card lists before collapsing the rest into a count.
CARD_LIMIT = 8


def _task_name(call: AgentTaskCall) -> str:
    definition = getattr(call, "task_definition", None)
    if definition is not None and definition.name:
        return definition.name
    version = getattr(call, "task_definition_version", None)
    if version is not None and version.task_definition is not None:
        return version.task_definition.name
    return f"call #{call.pk}"


def _message_text(args: Any) -> str:
    """Extract readable text from a parked ingest call's arguments."""
    if not isinstance(args, dict):
        return ""
    message = args.get("message")
    if isinstance(message, str):
        return message.strip()
    texts: list[str] = []
    if isinstance(message, (list, tuple)):
        for entry in message:
            if isinstance(entry, str):
                texts.append(entry)
            elif isinstance(entry, dict):
                for part in entry.get("parts") or []:
                    if isinstance(part, dict) and isinstance(part.get("content"), str):
                        texts.append(part["content"])
    text = "\n".join(item for item in texts if item.strip()).strip()
    if text:
        return text
    try:
        return json.dumps(args, indent=2, ensure_ascii=False, default=str)[:2000]
    except (TypeError, ValueError):
        return str(args)[:2000]


def queue_text(call: AgentTaskCall) -> str:
    """Readable text of a parked queue call (used by the combine action)."""
    return _message_text(call.carguments_json)


def _queue_rows(calls: list[AgentTaskCall], model_name: str) -> list[dict[str, Any]]:
    rows = []
    for call in calls:
        rows.append(
            {
                "pk": call.pk,
                "text": _message_text(call.carguments_json),
                "model": model_name,
                "created_at": call.created_at,
            }
        )
    return rows


def _question_items(calls: list[AgentTaskCall]) -> list[dict[str, Any]]:
    """Flatten every pending ``ask_user`` call into template-ready questions."""
    items: list[dict[str, Any]] = []
    for call in calls:
        args = call.carguments_json or {}
        # Resolve any GenericContent references in the stored arguments
        args = resolve_generic_content_refs(args)
        answers = args.get("answers") or {}
        for qidx, question in enumerate(normalize_questions(args.get("questions"))):
            raw = answers.get(question["question"])
            if isinstance(raw, list):
                answer_text = ", ".join(str(value) for value in raw)
            elif raw:
                answer_text = str(raw)
            else:
                answer_text = ""
            items.append(
                {
                    "call_pk": call.pk,
                    "qidx": qidx,
                    "header": question["header"],
                    "question": question["question"],
                    "multi": question["multiSelect"],
                    "options": [
                        {
                            "oidx": oidx,
                            "label": option["label"],
                            "description": option["description"],
                        }
                        for oidx, option in enumerate(question["options"])
                    ],
                    "answered": bool(answer_text),
                    "answer_text": answer_text,
                }
            )
    return items


def _approval_rows(calls: list[AgentTaskCall]) -> list[dict[str, Any]]:
    rows = []
    for call in calls:
        args = call.carguments_json or {}
        arguments = []
        if isinstance(args, dict):
            for key, value in args.items():
                if key in ("guardrail_reason", "*"):
                    continue
                if isinstance(value, (dict, list)):
                    try:
                        value = json.dumps(value, indent=2, ensure_ascii=False, default=str)
                    except (TypeError, ValueError):
                        value = str(value)
                arguments.append({"key": key, "value": value})
        rows.append(
            {
                "pk": call.pk,
                "name": _task_name(call),
                "reason": call.guardrail_reason or "",
                "arguments": arguments,
                "auto_status": (call.auto_review_status or "").lower(),
                "auto_reason": call.auto_review_reason or "",
                "created_at": call.created_at,
            }
        )
    return rows


def _humanize_seconds(seconds: int) -> str:
    minutes, secs = divmod(max(int(seconds), 0), 60)
    if minutes and secs:
        return f"{minutes}m {secs}s"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def _ratelimit_info(session_model, calls: list[AgentTaskCall]) -> dict[str, Any]:
    """Describe the model/key the parked calls are waiting for.

    Mirrors the legacy rate-limit card: it lists the blocked model's keys,
    alternative providers for the same model, other models, and the session's
    auto-failover policy so the user can switch without leaving the chat.
    """
    info: dict[str, Any] = {
        "count": len(calls),
        "model": "",
        "provider": "",
        "wait_text": "",
        "resuming": False,
        "keys": [],
        "providers": [],
        "models": [],
        "auto_failover": False,
        "max_wait": 0,
        "has_alternatives": False,
    }
    if not calls:
        return info
    try:
        runtime = session_model.get_runtime()
    except Exception:  # pylint: disable=broad-exception-caught
        return info
    try:
        aimodel = runtime.aimodel
    except Exception:  # pylint: disable=broad-exception-caught
        aimodel = None
    if aimodel is None:
        return info

    info["model"] = aimodel.name
    provider = getattr(aimodel, "api_provider", None)
    if provider is not None:
        info["provider"] = provider.name

    try:
        policy = runtime.key_failover_policy()
        info["auto_failover"] = bool(policy.auto_failover)
        info["max_wait"] = int(policy.max_wait_seconds or 0)
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    now = timezone.now()
    try:
        current = runtime.current_provider_api_key(aimodel)
    except Exception:  # pylint: disable=broad-exception-caught
        current = None
    if current is not None and current.rate_limit_until and current.rate_limit_until > now:
        info["wait_text"] = _humanize_seconds(
            (current.rate_limit_until - now).total_seconds()
        )
    elif provider is not None:
        waits = [
            int((key.rate_limit_until - now).total_seconds())
            for key in provider.api_keys.filter(enabled=True)
            if key.rate_limit_until and key.rate_limit_until > now
        ]
        if waits:
            info["wait_text"] = _humanize_seconds(min(waits))
        elif info["auto_failover"] or current is not None:
            info["resuming"] = True

    # API keys of the blocked provider.
    if provider is not None:
        try:
            keys = list(provider.api_keys.filter(enabled=True).order_by("pk"))
        except Exception:  # pylint: disable=broad-exception-caught
            keys = []
        for key in keys:
            is_current = current is not None and key.pk == current.pk
            cooling = bool(key.rate_limit_until and key.rate_limit_until > now)
            bits: list[str] = []
            if is_current:
                bits.append("current")
            if cooling:
                bits.append(
                    "cooling "
                    + _humanize_seconds((key.rate_limit_until - now).total_seconds())
                )
            elif not is_current:
                bits.append("ready")
            info["keys"].append(
                {
                    "pk": key.pk,
                    "label": getattr(key, "comment", "") or f"key {key.pk}",
                    "status": " · ".join(bits) or "ready",
                    "current": is_current,
                }
            )

    # Alternative providers serving the same model.
    try:
        from runtime.session.aimodel_picker import sibling_aimodels

        seen_providers: set[int] = set()
        for sibling in sibling_aimodels(aimodel):
            sibling_provider = getattr(sibling, "api_provider", None)
            if sibling_provider is None or sibling_provider.pk in seen_providers:
                continue
            seen_providers.add(sibling_provider.pk)
            enabled = list(sibling_provider.api_keys.filter(enabled=True))
            keys_text = f"{len(enabled)} key" + ("s" if len(enabled) != 1 else "")
            if any(k.rate_limit_until and k.rate_limit_until > now for k in enabled):
                keys_text += " · cooling"
            info["providers"].append(
                {
                    "pk": sibling_provider.pk,
                    "name": sibling_provider.name,
                    "keys_text": keys_text,
                }
            )
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    # Other models entirely.
    try:
        from runtime.session.aimodel_picker import model_groups

        for group in model_groups():
            if group.name == aimodel.name:
                continue
            plural = "s" if group.provider_count != 1 else ""
            info["models"].append(
                {
                    "name": group.name,
                    "providers_text": f"{group.provider_count} provider{plural}",
                }
            )
            if len(info["models"]) >= 6:
                break
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    info["has_alternatives"] = bool(
        info["providers"] or info["models"] or len(info["keys"]) > 1
    )
    return info


def build_chat_cards(session_model) -> dict[str, Any]:
    """Return the status-card context for *session_model*."""
    # Only the parked/halted calls can ever appear on a status card, so filter
    # at the DB level instead of hydrating every call of (potentially huge)
    # sessions — 60k+ calls here would otherwise dominate render time.
    calls = list(
        AgentTaskCall.objects.filter(
            session=session_model,
            status_detail__in=(
                TaskCallStatusDetail.WAITING_QUEUE,
                TaskCallStatusDetail.HALTED_APPROVAL,
                TaskCallStatusDetail.WAITING_RATELIMIT,
            ),
        )
        .select_related("task_definition", "task_definition_version__task_definition")
        .order_by("created_at")
    )
    queued = [
        call for call in calls
        if call.status_detail == TaskCallStatusDetail.WAITING_QUEUE
    ]
    halted = [
        call for call in calls
        if call.status_detail == TaskCallStatusDetail.HALTED_APPROVAL
    ]
    ratelimited = [
        call for call in calls
        if call.status_detail == TaskCallStatusDetail.WAITING_RATELIMIT
    ]
    question_calls = [call for call in halted if _task_name(call) == ASK_USER_TOOL_NAME]
    approval_calls = [call for call in halted if _task_name(call) != ASK_USER_TOOL_NAME]

    model_name = ""
    turn_limit = {"active": False, "current": 0, "maximum": 0}
    try:
        runtime = session_model.get_runtime()
        aimodel = runtime.aimodel
        model_name = aimodel.name if aimodel is not None else ""
        turn_limit = {
            "active": bool(
                runtime.max_unattended_turns
                and (session_model.unattended_turn_count or 0) >= runtime.max_unattended_turns
            ),
            "current": session_model.unattended_turn_count or 0,
            "maximum": runtime.max_unattended_turns or 0,
        }
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    return {
        "queue": {
            "rows": _queue_rows(queued[:CARD_LIMIT], model_name),
            "count": len(queued),
            "remaining": max(len(queued) - CARD_LIMIT, 0),
        },
        "questions": {
            "items": _question_items(question_calls),
            "calls": [{"pk": call.pk, "name": _task_name(call)} for call in question_calls],
        },
        "approvals": {
            "rows": _approval_rows(approval_calls[:CARD_LIMIT]),
            "count": len(approval_calls),
            "remaining": max(len(approval_calls) - CARD_LIMIT, 0),
        },
        "turn_limit": turn_limit,
        "ratelimit": _ratelimit_info(session_model, ratelimited),
    }
