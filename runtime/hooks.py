"""Session hooks — per-call intercepts declared as agent manifest ``hooks:``.

See ``docs/session-hooks.md``. Hooks are ``before:``/``after:`` entries on
the session agent's tasks, applied around every intercepted call:

- ``before`` entries transform the call's input (kwargs) — ``inline``
  (blocking chain via arg references) or ``detached`` (fire-and-forget with
  a snapshot of the original args).
- ``after`` entries transform the call's result — ``inline`` (the parent
  waits via ``WAITING_SUBTASKS_OR_HOOKS``) or ``detached``.

There are no bespoke lifecycle events any more. Session end is the
``session_end`` *task* (`.agentone/scripts/core/session_end.py`), so it is
hooked like any other call with ``after: ... match: {name: session_end}``;
compaction is the ``compact_turn`` chain, hooked with ``before:``/``after:``.
"""
from __future__ import annotations

import fnmatch
import re
from typing import Any

from server.models.enums.session_enums import SessionType


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
    session_type: Any = None,
) -> bool:
    """Return whether an intercept entry fires for a given call.

    All declared ``match:`` dimensions must match (AND); omitted dimensions
    are wildcards. ``match.type`` compares case-insensitively against the
    call's ``TaskType`` and ``match.session_type`` case-insensitively against
    the session's ``SessionType``; the rest are glob matches (``*`` = all,
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
    want_session_type = match.get("session_type")
    if want_session_type is not None and not _glob_match(
        str(session_type or "").lower(), str(want_session_type).lower()
    ):
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
            session_type=ctx.get("session_type"),
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
