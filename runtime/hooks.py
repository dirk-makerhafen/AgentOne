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

import fnmatch
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

#: Execution modes for per-call intercept hooks (``before:``/``after:``
#: entries): ``inline`` blocks the intercepted call (transform contract —
#: hook receives the original input and must return a compatible structure,
#: pass-through to allow unmodified), ``detached`` fires and forgets
#: (return ignored, parent never waits). Both positions support both modes.
INTERCEPT_MODES: tuple[str, ...] = ("inline", "detached")

#: Failure policies for intercept hooks: ``fail_closed`` blocks/cancels the
#: parent on hook failure, ``fail_open`` lets the parent proceed. Inline
#: ``before`` hooks are always ``fail_closed`` (a failed input transform has
#: no sound fallback — enforced by the loader).
INTERCEPT_ON_ERRORS: tuple[str, ...] = ("fail_open", "fail_closed")


def _split_alternatives(pattern: Any) -> list[str]:
    """Split a match pattern into ``|``/``,``-separated glob alternatives."""
    if pattern is None:
        return []
    if isinstance(pattern, (list, tuple)):
        out: list[str] = []
        for item in pattern:
            out.extend(_split_alternatives(item))
        return out
    return [t.strip() for t in re.split(r"[|,]", str(pattern)) if t.strip()]


def _glob_match(value: Any, pattern: Any) -> bool:
    """Return whether *value* matches the glob *pattern* (``*`` = all).

    An absent/empty pattern matches everything so omitted ``match:``
    dimensions stay wildcards.
    """
    alternatives = _split_alternatives(pattern)
    if not alternatives:
        return True
    text = "" if value is None else str(value)
    return any(fnmatch.fnmatch(text, alt) for alt in alternatives)


def matches_call_hook(
    entry: dict[str, Any],
    *,
    def_name: Any,
    def_type: Any = None,
    session_name: Any = None,
) -> bool:
    """Return whether an intercept entry fires for a given call.

    All declared ``match:`` dimensions must match (AND); omitted dimensions
    are wildcards. ``match.type`` compares case-insensitively against the
    call's ``TaskType``; the rest are glob matches (``*`` = all,
    ``"main-* | scratch"`` = alternation).
    """
    if not isinstance(entry, dict):
        return False
    if "before" not in entry and "after" not in entry:
        return False
    match = entry.get("match") or {}
    if isinstance(match, str):
        match = {"name": match}
    if not isinstance(match, dict):
        return False
    if not _glob_match(def_name, match.get("name")):
        return False
    want_type = match.get("type")
    if want_type is not None and str(want_type).upper() != str(def_type or "").upper():
        return False
    if not _glob_match(session_name, match.get("session")):
        return False
    return True


def intercept_entries(entries: Any, position: str) -> list[dict[str, Any]]:
    """Return intercept entries for *position* (``"before"``/``"after"``) in order."""
    if not entries:
        return []
    return [e for e in entries if isinstance(e, dict) and position in e]


def hook_task_names(entries: Any) -> set[str]:
    """Return task names owned by intercept entries (recursion guard set)."""
    names: set[str] = set()
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        for key in ("before", "after"):
            task = entry.get(key)
            if isinstance(task, str) and task.strip():
                names.add(task.strip())
    return names


def get_session_agent_hooks(session_version: Any) -> list[dict[str, Any]]:
    """Return merged hook entries for a session version's agent.

    Resolves through the extends chain like the runtime ``Agent.hooks``
    property. Never raises — unresolvable agents read as no hooks.
    """
    try:
        from runtime.agents.agent import Agent

        agent_model = getattr(session_version, "agent", None)
        if agent_model is None:
            return []
        pinned = getattr(session_version, "pinned_agent_version", None)
        return Agent(agent_model=agent_model, pinned_agent_version=pinned).hooks
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"[hooks] cannot resolve agent hooks: {e}")
        return []


def call_match_context(task_instance: Any) -> dict[str, Any]:
    """Build the match dimensions for a task instance's next call."""
    tdv = getattr(task_instance, "task_definition_version", None)
    definition = getattr(tdv, "task_definition", None) if tdv is not None else None
    if definition is None:
        definition = getattr(task_instance, "task_definition", None)
    def_name = getattr(definition, "name", "") if definition is not None else ""
    def_type = getattr(tdv, "task_type", "") if tdv is not None else ""
    session = getattr(task_instance, "session", None)
    session_name = getattr(session, "name", "") if session is not None else ""
    return {
        "def_name": def_name,
        "def_type": def_type,
        "session_name": session_name,
        "session_type": getattr(session, "session_type", "") if session is not None else "",
    }


def matching_intercepts(
    entries: Any, position: str, ctx: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return ordered intercept entries firing for a call context.

    Applies two guards: framework worker forks (``SUBTASK_HOOK``,
    ``SUBTASK_COMPACT``) never fire intercepts, and when the intercepted
    call *is* a hook task itself, no intercept fires (hook tasks never
    trigger intercepts).
    """
    candidates = intercept_entries(entries, position)
    if not candidates:
        return []
    if ctx.get("session_type") in (
        SessionType.SUBTASK_HOOK.value,
        SessionType.SUBTASK_COMPACT.value,
    ):
        return []
    if ctx.get("def_name") in hook_task_names(entries):
        return []
    return [
        e
        for e in candidates
        if matches_call_hook(
            e,
            def_name=ctx.get("def_name"),
            def_type=ctx.get("def_type"),
            session_name=ctx.get("session_name"),
        )
    ]


def build_hook_task_instance(session_version: Any, task_name: str) -> Any | None:
    """Build a ``TaskInstance`` for an intercept hook task (same session).

    Resolves *task_name* to the session agent's task definition (any
    ``TaskType``), preferring agent-owned definitions over global ones.
    Returns ``None`` when unresolvable (caller skips with a log line).
    """
    try:
        from server.models.tasks.task_definition import TaskDefinition
        from server.models.tasks.task_instance import TaskInstance

        session_agent = getattr(session_version, "agent", None)
        agent_id = getattr(session_agent, "pk", None)
        candidates = list(
            TaskDefinition.objects.filter(name=task_name).select_related("parent_agent")
        )
        definition = None
        for candidate in candidates:
            if getattr(candidate, "parent_agent_id", None) == agent_id and agent_id is not None:
                definition = candidate
                break
        if definition is None:
            for candidate in candidates:
                if getattr(candidate, "parent_agent_id", None) is None:
                    definition = candidate
                    break
        if definition is None and candidates:
            definition = candidates[0]
        if definition is None:
            print(f"[hooks] intercept task {task_name!r} not found — skipped")
            return None
        latest = getattr(definition, "latest_task_version", None)
        if latest is None:
            print(f"[hooks] intercept task {task_name!r} has no version — skipped")
            return None
        return TaskInstance.get_or_create(
            task_definition=latest,
            session_version=session_version,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"[hooks] cannot build intercept task {task_name!r}: {e}")
        return None


def after_hook_failed_open(parent_call_id: int, hook_run_id: int) -> bool:
    """Return whether a failed after-hook call should not cancel its parent.

    Looks up the hook call behind *hook_run_id* and checks the matching
    intercept entry's ``on_error`` policy. Static (M2M-wired) hooks and
    unknown calls read as ``fail_closed`` (existing behavior preserved).
    """
    try:
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.tasks.agent_task_run import AgentTaskRun

        try:
            run = AgentTaskRun.objects.select_related(
                "agent_task_call__task_definition"
            ).get(pk=hook_run_id)
        except AgentTaskRun.DoesNotExist:
            return False
        hook_call = run.agent_task_call
        if hook_call is None:
            return False
        hook_name = getattr(hook_call.task_definition, "name", None)
        if not hook_name:
            return False
        parent = AgentTaskCall.objects.filter(pk=parent_call_id).first()
        if parent is None:
            return False
        entries = get_session_agent_hooks(parent.session_version)
        for entry in entries:
            if entry.get("after") == hook_name and entry.get("on_error") == "fail_open":
                return True
        return False
    except Exception:  # pylint: disable=broad-exception-caught
        return False


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
