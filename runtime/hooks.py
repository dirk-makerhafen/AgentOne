"""Session hooks — detached agent work at lifecycle points.

See ``docs/session-hooks.md`` for the design. Single entry point::

    maybe_fire_hooks(session, event, ctx)

resolves the parent agent's ``hooks:`` entries for *event*, evaluates
matchers, builds a ``SUBTASK_HOOK`` fork anchored at the event's snapshot
message, enforces the token budget (prefix compaction when over), and
dispatches the hook task detached — the parent never waits. An optional
``ingest`` task runs parent-side on the fork result via auto-await.

Async-tier only: nothing here blocks, vetoes, or injects into the live turn.
Hook forks never refire hooks (``SUBTASK_HOOK`` type gate).
"""
from __future__ import annotations

import re
import time
import traceback
from datetime import timedelta
from typing import Any

from django.utils import timezone

from server.models.enums.session_enums import SessionType


#: Lifecycle events and the context field each event's matcher tests.
#: A matcher fires when it fullmatches ANY listed field (so ``".*"``
#: matches everything and ``"allowlist_violation"`` matches a session_end
#: reason while ``"session"`` matches the type).
HOOK_EVENTS: dict[str, tuple[str, ...]] = {
    "stop": ("session_type",),
    "pre_compact": ("trigger",),
    "post_compact": ("trigger",),
    "session_end": ("session_type", "reason"),
}

#: Matcher used when an entry declares none.
DEFAULT_MATCHERS: dict[str, str] = {
    "stop": r"session|subsession",
    "pre_compact": r"auto|idle",
    "post_compact": r"auto|idle",
    "session_end": r"session|subsession",
}


def matches(matcher: str | None, event: str, ctx: dict[str, Any]) -> bool:
    """Return whether *matcher* fires for *event* with context *ctx*."""
    pattern = matcher or DEFAULT_MATCHERS[event]
    try:
        rx = re.compile(pattern)
    except re.error:
        return False
    for field in HOOK_EVENTS[event]:
        value = ctx.get(field)
        if value is not None and rx.fullmatch(str(value)):
            return True
    return False


def _hook_context(session: Any, event: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Build the full matcher + snapshot context for a firing."""
    full = {
        "session_type": session.session_type,
        "trigger": ctx.get("trigger", ""),
        "reason": ctx.get("reason", ""),
    }
    full.update({k: v for k, v in ctx.items() if k not in full})
    return full


def maybe_fire_hooks(session: Any, event: str, ctx: dict[str, Any] | None = None) -> list:
    """Fire matching hook entries for *event* in detached forks.

    *session* is the parent runtime ``Session``; *ctx* carries event facts
    (anchor pks, trigger, reason — see ``docs/session-hooks.md`` §5).
    Never raises: per-hook errors are logged and skipped (fail-open —
    hooks must never break the turn they observe). Returns the created
    ``SessionHookRun`` rows.
    """
    from server.models.hooks.hook_run import SessionHookRun

    ctx = dict(ctx or {})
    if event not in HOOK_EVENTS:
        print(f"[hooks] unknown event {event!r} — ignored")
        return []
    # Recursion gate: hook forks never fire hooks, independent of settings.
    if session.session_type == SessionType.SUBTASK_HOOK.value:
        return []
    full_ctx = _hook_context(session, event, ctx)
    runs = []
    try:
        entries = session.agent.hooks
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"[hooks] cannot resolve hooks for {session.agent.name}: {e}")
        return []
    for hook in entries:
        if not isinstance(hook, dict) or hook.get("on") != event:
            continue
        if not matches(hook.get("matcher"), event, full_ctx):
            continue
        try:
            run = _fire_one(session, hook, full_ctx)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(
                f"[hooks] error firing {hook.get('name')} on {event} "
                f"for session {session.model.pk}: {e} {traceback.format_exc()}"
            )
            continue
        if run is not None:
            runs.append(run)
    return runs


def _in_flight(session: Any, hook_name: str) -> bool:
    """Return whether a non-ended run exists for (session, hook)."""
    from server.models.enums.task_enums import TaskCallStatus
    from server.models.hooks.hook_run import SessionHookRun

    for run in SessionHookRun.objects.filter(
        session_id=session.model.pk, hook_name=hook_name, status="dispatched"
    ):
        if run.root_call_id is None:
            return True
        try:
            if run.root_call.status != TaskCallStatus.ENDED:
                return True
        except Exception:  # pylint: disable=broad-exception-caught
            return True
    return False


def _fire_one(session: Any, hook: dict, ctx: dict[str, Any]) -> Any | None:
    """Build the fork and dispatch one hook entry. Returns the run row."""
    from django.utils import timezone as tz

    from server.models.agents.agent import AgentModel
    from server.models.enums.message_enums import MessageRole
    from server.models.hooks.hook_run import SessionHookRun
    from server.models.message import Message

    hook_name = hook.get("name") or hook.get("task")
    if _in_flight(session, hook_name):
        return None

    # Resolve the hook agent (default: the parent agent itself).
    agent_name = hook.get("agent") or session.agent.name
    agent_model = AgentModel.objects.filter(name=agent_name).first()
    if agent_model is None:
        print(f"[hooks] hook {hook_name!r}: agent {agent_name!r} not found — skipped")
        return None
    agent_version = agent_model.latest_agent_version
    if agent_version is None:
        print(f"[hooks] hook {hook_name!r}: agent {agent_name!r} has no version — skipped")
        return None

    # Snapshot anchor: the message the fork links to. Fixed at dispatch —
    # later parent messages are invisible to the fork by construction.
    anchor = ctx.get("anchor_message")
    if anchor is not None and not isinstance(anchor, Message):
        anchor = Message.objects.filter(pk=anchor).first()

    # Fork pins: no auto-compaction (the fork must never compact itself
    # mid-reflection) and no idle compaction. Hooks need no pin — the
    # SUBTASK_HOOK type gate in maybe_fire_hooks covers recursion.
    # (Auto-compact pins are-off here means *reactive/idle* triggers only;
    # direct compact_turn dispatch for the budget prefix still works.)
    fork_kwargs = {
        "name": f"p{session.model.pk}:hook:{hook_name}:{int(time.time())}",
        "description": f"Session hook {hook_name!r} ({hook.get('on')}) for {session.name}",
        "session_type": SessionType.SUBTASK_HOOK,
        "auto_compact_max_tokens": 0,
        "auto_compact_idle_seconds": 0,
        "anchor": anchor,
    }
    # Same agent → full fork (inherit settings + links); a different hook
    # agent → clean subagent session (its own settings, explicit pins only).
    if agent_name == session.agent.name:
        fork = session.fork(**fork_kwargs)
    else:
        fork = session.spawn_subagent(agent_version, **fork_kwargs)
    # Persist the two hook-framing messages without running a turn; the call
    # is a promise for the last of them, which the hook/compact tasks consume
    # via auto-await (``message=persist_call``).
    persist_call = fork.add_user_message(

        f"You are a session-hook worker ({hook_name!r}, event "
        f"{hook.get('on')!r}) forked from parent session "
        f"#{session.model.pk} of agent '{session.agent.name}'. "
        f"Do the hook task below, then call final_result with a short "
        f"report of what you did.",
    
        f"Hook job: run task {hook['task']!r} for event {hook.get('on')!r} "
        f"(parent session #{session.model.pk}).",
        execute_turn=False,
    )

    # Token budget: estimate the fork's inherited context from the anchor on
    # the parent. Over budget with a compactable boundary → prefix-compact
    # the fork first (reuse compact_turn); the hook task waits on it via a
    # call-reference kwarg (native WAITING_DEPENDENCY). Hook tasks must
    # accept **kwargs — universal convention for script functions/chains.
    compact_call = None
    max_tokens = hook.get("max_tokens") or 0
    if max_tokens > 0 and anchor is not None:
        from runtime.history_limiter import (
            estimate_entries_tokens,
            find_compaction_boundary,
            walk_compaction_entries,
        )

        entries = walk_compaction_entries(session, anchor)
        if estimate_entries_tokens(entries) > max_tokens and (
            find_compaction_boundary(session, anchor) is not None
        ):
            compact_task = fork.get_task("compact_turn")
            if compact_task is not None:
                compact_call = compact_task.delay(message=persist_call)

    hook_task = fork.get_task(hook["task"])
    if hook_task is None:
        print(
            f"[hooks] hook {hook_name!r}: task {hook['task']!r} not available "
            f"to agent {agent_name!r} — skipped"
        )
        return None
    hook_kwargs: dict[str, Any] = {
        "message": persist_call,
        "hook_ctx": _json_ctx(session, hook, ctx, anchor),
    }
    if compact_call is not None:
        hook_kwargs["hook_after"] = compact_call
    hook_call = hook_task.delay(**hook_kwargs)

    timeout_seconds = hook.get("timeout_seconds") or 0
    deadline = (tz.now() + timedelta(seconds=timeout_seconds) if timeout_seconds > 0 else None)
    run = SessionHookRun.objects.create(
        session=session.model,
        hook_name=hook_name,
        event=hook.get("on"),
        anchor_message=anchor,
        root_call=hook_call,
        deadline=deadline,
        status="dispatched",
    )

    # Optional parent-side ingest: runs in the parent on the fork result via
    # auto-await (``result=`` carries the call reference, as in
    # spawn_subtask). A quick synchronous write, not an agent turn.
    ingest_name = hook.get("ingest")
    if ingest_name:
        ingest_task = session.get_task(ingest_name)
        if ingest_task is None:
            print(
                f"[hooks] hook {hook_name!r}: ingest task {ingest_name!r} not "
                f"available to agent {session.agent.name!r} — skipped"
            )
        else:
            ingest_task.delay(
                hook_name=hook_name,
                event=hook.get("on"),
                hook_ctx=_json_ctx(session, hook, ctx, anchor),
                result=hook_call,
            )
    return run


def _json_ctx(
    session: Any, hook: dict, ctx: dict[str, Any], anchor: Any
) -> dict[str, Any]:
    """Build the JSON-safe hook context passed to hook/ingest tasks."""
    return {
        "hook": hook.get("name"),
        "event": hook.get("on"),
        "parent_session_pk": session.model.pk,
        "parent_agent": session.agent.name,
        "anchor_message_pk": anchor.pk if anchor is not None else None,
        "trigger": ctx.get("trigger", ""),
        "reason": ctx.get("reason", ""),
    }


def reap_hook_timeouts(limit: int = 20) -> int:
    """Cancel expired hook runs; delete finished ones. Returns reaped count.

    Called from the tick (``_reap_hook_timeouts``). Never applies the 24h
    ``_is_ancient`` turn-death guard — the deadline *is* the lifetime.
    """
    from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
    from server.models.hooks.hook_run import SessionHookRun
    from server.models.tasks.agent_task_call import AgentTaskCall
    from server.models.tasks.agent_task_run import AgentTaskRun
    from runtime.tasks.call_fsm import TaskCallStateMachine
    from runtime.tasks.call_scheduler import CallScheduler

    now = timezone.now()
    reaped = 0

    for run in SessionHookRun.objects.filter(status="dispatched").order_by("deadline"):
        if reaped >= limit:
            break
        try:
            if run.root_call_id is None:
                run.delete()
                reaped += 1
                continue
            call = AgentTaskCall.objects.filter(pk=run.root_call_id).first()
            if call is None or call.status == TaskCallStatus.ENDED:
                run.delete()  # root ended — row served its purpose
                reaped += 1
                continue
            if run.deadline is not None and run.deadline <= now:
                last_run = (
                    AgentTaskRun.objects.filter(agent_task_call_id=call.pk)
                    .order_by("-pk")
                    .first()
                )
                # ``status_detail`` reads back as a plain str — coerce for the
                # FSM, which expects the enum member.
                from_detail = call.status_detail
                if isinstance(from_detail, str):
                    from_detail = TaskCallStatusDetail(from_detail)
                if TaskCallStateMachine.transition(
                    call.pk,
                    from_detail,
                    TaskCallStatusDetail.ENDED_CANCELLED,
                    extra={"ended_at": now},
                ):
                    CallScheduler._on_taskcall_ended(
                        call.pk,
                        last_run.pk if last_run else 0,
                        TaskCallStatusDetail.ENDED_CANCELLED,
                    )
                SessionHookRun.objects.filter(pk=run.pk).update(status="expired")
                reaped += 1
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[hooks] error reaping hook run {run.pk}: {e}")
    return reaped


def delete_expired_hook_runs(days: int = 7) -> int:
    """Delete ``expired`` runs older than *days* (audit-trail hygiene)."""
    from server.models.hooks.hook_run import SessionHookRun

    cutoff = timezone.now() - timedelta(days=days)
    count, _ = SessionHookRun.objects.filter(
        status="expired", updated_at__lt=cutoff
    ).delete()
    return count
