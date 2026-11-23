"""Draft: long-running memory merge worker sessions.

This is an initial draft of the "memory merge v2" flow discussed in chat.
It is intentionally **not** wired into ``scripts.md`` yet.

High-level idea
===============

Instead of spawning two short-lived synthesizer subtasks per pending node,
maintain long-running merge sessions per memory node (and, eventually, per
kind: memory/reflections).  Memory updates are pushed as small deltas.

The flow sketched by the user:

1. ``memory_update_dispatcher`` (memory-manage task/tool)
   - Called when memory files have been updated and committed.
   - Args: path, git hash (and optionally node/kind metadata).
   - Creates/lookups the matching memory merge agent session.
   - Calls ``memory_updated(path, latest_hash)`` on that merge session.

2. ``memory_updated`` (merge-agent task)
   - Records the latest reported git hash in the merge session's private
     workspace (session-private storage, not memory tree).
   - Looks up ``trigger_merge`` task on the merge session.
   - If active/pending ``trigger_merge`` calls < 2, dispatches
     ``trigger_merge()``.

3. ``trigger_merge`` (merge-agent task)
   - Reads latest reported hash/cursor from session-private storage.
   - Determines whether memory, reflections, or both changed since last
     processed cursor.
   - Builds a small prompt containing diff or full content (whichever is
     smaller), never instructing the agent to read source files.
   - Calls ``ingest_user_message`` / ``session.add_user_message`` with that
     prompt.
   - Passes the ingest result and target hash to
     ``finalize_memory_merge(...)``.

4. ``finalize_memory_merge`` (merge-agent task)
   - Waits for synthesis result (auto-awaited arg reference when dispatched as
     task call).
   - Validates outputs, commits/stores hashes/cursors, advances manifest state.
   - If it produced changes that affect parent nodes, calls
     ``memory_update_dispatcher`` for those parents.

This draft keeps the code in one file for discussion.  Before implementation,
split responsibilities between memory-manage (dispatcher/finalizer authority)
and a dedicated merge-worker agent.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import git as memgit
import paths as mempaths
import sources as memsources

# Reuse existing prompt/content helpers from v1 for the first draft.
from memory_merge import (
    KIND_OUTPUT,
    OUTPUT_FILES,
    SOURCE_NAMES,
    SYNTHESIZER_DISALLOWED_TASKS,
    SYNTHESIZER_DISALLOWED_TOOLS,
    SYNTHESIZER_MAX_TURNS,
    SYNTHESIZER_TOOL_ALLOWLIST,
    _access_overrides,
    _format_sources,
    build_prompt,
)

MERGE_AGENT_NAME = "memory-manage"  # TODO: replace with dedicated internal merge agent.
MERGE_GROUP_PREFIX = "memorymerge"
MERGE_MAX_PENDING_TRIGGER_CALLS = 2

STATE_FILENAME = "memory_merge_state.json"
LATEST_HASH_FILENAME = "memory_merge_latest_hash.txt"


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _ok(status: str = "success", **payload: Any) -> tuple[bool, dict[str, Any]]:
    return True, {"status": status, **payload}


def _err(message: str, *, status: str = "error", **payload: Any) -> tuple[bool, dict[str, Any]]:
    return False, {"status": status, "message": message, **payload}


def _normalize_path(value: Any) -> Path:
    return Path(str(value or "")).expanduser().resolve()


def _manifest_dir(manifest_or_dir: Any) -> Path:
    path = _normalize_path(manifest_or_dir)
    if path.name == memsources.SOURCES_FILENAME:
        return path.parent
    return path


def _manifest_path(manifest_or_dir: Any) -> Path:
    target_dir = _manifest_dir(manifest_or_dir)
    return target_dir / memsources.SOURCES_FILENAME


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _session_private_dir(session: Any) -> Path:
    ensure = getattr(session, "ensure_private_dir", None)
    if callable(ensure):
        return Path(ensure())
    private_dir = getattr(session, "private_dir", None)
    if private_dir is not None:
        return Path(private_dir)
    raise RuntimeError("session has no private dir")


def _state_path(session: Any) -> Path:
    return _session_private_dir(session) / STATE_FILENAME


def _latest_hash_path(session: Any) -> Path:
    return _session_private_dir(session) / LATEST_HASH_FILENAME


def _load_state(session: Any) -> dict[str, Any]:
    data = _read_json(_state_path(session), {})
    return data if isinstance(data, dict) else {}


def _save_state(session: Any, state: dict[str, Any]) -> None:
    _write_json(_state_path(session), state)


def _record_latest_hash(session: Any, manifest_path: Path, git_hash: str | None) -> dict[str, Any]:
    state = _load_state(session)
    state.update({
        "manifest_path": manifest_path.as_posix(),
        "target_dir": manifest_path.parent.as_posix(),
        "latest_reported_hash": git_hash,
        "latest_reported_at": time.time(),
    })
    _save_state(session, state)
    # Also keep a tiny plain-text file for easy debugging / shell inspection.
    try:
        _latest_hash_path(session).write_text((git_hash or "") + "\n", encoding="utf-8")
    except OSError:
        pass
    return state


# ---------------------------------------------------------------------------
# Session / task lookup
# ---------------------------------------------------------------------------


def _node_kind(manifest_path: Path) -> str:
    payload = memsources.read_sources(manifest_path)
    return str(payload.get("type") or payload.get("kind") or "memory").strip() or "memory"


def _merge_session_name(manifest_path: Path, kind: str) -> str:
    digest = hashlib.sha1(manifest_path.as_posix().encode("utf-8")).hexdigest()[:16]
    return f"{MERGE_GROUP_PREFIX}:{kind}:{digest}"


def _active_or_pending_call_count(session: Any, task_name: str) -> int:
    """Count NEW/WAITING/ACTIVE calls for *task_name* in *session*.

    Draft implementation uses DB state directly.  It intentionally includes
    WAITING because waiting calls still represent queued/incomplete work.
    """
    try:
        from server.models.enums.task_enums import TaskCallStatus
        from server.models.tasks.agent_task_call import AgentTaskCall
    except Exception:  # pylint: disable=broad-exception-caught
        return 0

    model = getattr(session, "model", None)
    if model is None:
        return 0
    try:
        return AgentTaskCall.objects.filter(
            session=model,
            task_definition_version__task_definition__name=task_name,
            status__in=[
                TaskCallStatus.NEW,
                TaskCallStatus.WAITING,
                TaskCallStatus.ACTIVE,
            ],
        ).count()
    except Exception:  # pylint: disable=broad-exception-caught
        return 0


def _get_or_create_merge_session(
    _session: Any,
    manifest_path: Path,
    *,
    kind: str = "node",
) -> Any | None:
    """Resolve/create a long-running merge worker session.

    TODO: this currently uses _session.spawn_subagent/resolve_agent_version.
    For a real implementation we likely want a dedicated internal agent with
    constrained tool access and its own task definitions.
    """
    target_dir = manifest_path.parent
    name = _merge_session_name(manifest_path, kind)
    node_kind = _node_kind(manifest_path)

    # Reuse existing session lookup by name+parent when possible.
    try:
        from runtime.session.session import Session
        from server.models.agents.agent import AgentModel
        from server.models.sessions.session import SessionModel

        parent = getattr(_session, "model", None)
        existing = SessionModel.objects.filter(name=name, parent_session=parent).first()
        if existing is not None:
            return Session(session_model=existing)
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    # Draft: spawn via existing subagent API.  access/tool restrictions should
    # be tightened once the merge agent/task layout is final.
    spawn = getattr(_session, "spawn_subagent", None)
    if callable(spawn):
        child = spawn(
            MERGE_AGENT_NAME,
            name=name,
            description=f"Memory merge worker for {manifest_path.as_posix()}",
            session_type="subtask_delegate",
            group_key=f"{MERGE_GROUP_PREFIX}:{kind}",
            allow_internal=True,
            access=_access_overrides(_session, target_dir, KIND_OUTPUT.get(kind, KIND_OUTPUT["memory"])),
            disallowedToolNames=SYNTHESIZER_DISALLOWED_TOOLS,
            disallowedTaskNames=SYNTHESIZER_DISALLOWED_TASKS,
            tool_call_allowlist=SYNTHESIZER_TOOL_ALLOWLIST,
            max_turns=SYNTHESIZER_MAX_TURNS,
        )
        if child is not None:
            state = _load_state(child)
            state.setdefault("manifest_path", manifest_path.as_posix())
            state.setdefault("target_dir", target_dir.as_posix())
            state.setdefault("node_kind", node_kind)
            state.setdefault("kind", kind)
            _save_state(child, state)
            return child

    # Fallback: direct model lookup, no session spawn.
    try:
        from server.models.agents.agent import AgentModel
        from runtime.session.session import Session

        agent_model = AgentModel.objects.filter(name=MERGE_AGENT_NAME).first()
        if agent_model is None:
            return None
        sv = agent_model.latest_agent_version.get_or_create_session(
            name=name,
            description=f"Memory merge worker for {manifest_path.as_posix()}",
            parent_session_version=_session.get_version_model() if hasattr(_session, "get_version_model") else None,
            session_type="subtask_delegate",
            group_key=f"{MERGE_GROUP_PREFIX}:{kind}",
        )
        child = Session(session_model=sv.session, pinned_session_version=sv)
        state = _load_state(child)
        state.setdefault("manifest_path", manifest_path.as_posix())
        state.setdefault("target_dir", target_dir.as_posix())
        state.setdefault("node_kind", node_kind)
        state.setdefault("kind", kind)
        _save_state(child, state)
        return child
    except Exception:  # pylint: disable=broad-exception-caught
        return None


# ---------------------------------------------------------------------------
# Dispatcher (memory-manage side)
# ---------------------------------------------------------------------------


def memory_update_dispatcher(
    _session: Any,
    path: str = "",
    git_hash: str = "",
    kind: str = "node",
) -> tuple[bool, dict[str, Any]]:
    """Entry point called when memory files were updated and committed.

    Draft contract:
        memory_update_dispatcher(path=<manifest_or_node_dir>, git_hash=<sha>)

    The dispatcher finds/creates the long-running merge session for that node
    and asks it to record the latest hash via ``memory_updated``.
    """
    if not path:
        return _err("path is required")

    manifest_path = _manifest_path(path)
    target_dir = manifest_path.parent
    if not target_dir.exists():
        return _err(f"memory node directory does not exist: {target_dir}")

    latest_hash = (git_hash or "").strip() or memgit.path_commit(target_dir)
    worker = _get_or_create_merge_session(_session, manifest_path, kind=kind)
    if worker is None:
        return _err("could not resolve/create merge worker session", agent=MERGE_AGENT_NAME)

    task = worker.get_task("memory_updated")
    if task is None:
        # Draft fallback: call directly when running in same process / tests.
        return memory_updated(worker, manifest_path.as_posix(), latest_hash or "")

    call = task.delay(manifest_path.as_posix(), latest_hash or "")
    return _ok(
        "dispatched",
        manifest_path=manifest_path.as_posix(),
        target_dir=target_dir.as_posix(),
        git_hash=latest_hash,
        worker_session_pk=getattr(getattr(worker, "model", None), "pk", None),
        memory_updated_call_pk=getattr(call, "pk", None),
    )


# ---------------------------------------------------------------------------
# Merge worker tasks
# ---------------------------------------------------------------------------


def memory_updated(
    _session: Any,
    memory_sources_md_path: str = "",
    latest_hash: str = "",
) -> tuple[bool, dict[str, Any]]:
    """Record a newly reported hash and maybe trigger merge work.

    This task is intended to run in the long-running merge worker session.
    """
    if not memory_sources_md_path:
        return _err("memory_sources_md_path is required")

    manifest_path = _manifest_path(memory_sources_md_path)
    latest_hash = (latest_hash or "").strip() or None
    state = _record_latest_hash(_session, manifest_path, latest_hash)

    trigger_task = _session.get_task("trigger_merge")
    active = _active_or_pending_call_count(_session, "trigger_merge")
    state["last_memory_updated_at"] = time.time()
    state["trigger_merge_active_or_pending"] = active

    if trigger_task is None:
        _save_state(_session, state)
        return _err("task 'trigger_merge' is not available to this session", **state)

    if active >= MERGE_MAX_PENDING_TRIGGER_CALLS:
        state["last_action"] = "congested"
        _save_state(_session, state)
        return _ok(
            "busy",
            message="trigger_merge queue is full; latest hash recorded",
            active_or_pending=active,
            limit=MERGE_MAX_PENDING_TRIGGER_CALLS,
            **state,
        )

    call = trigger_task.delay()
    state["last_action"] = "triggered"
    state["last_trigger_call_pk"] = getattr(call, "pk", None)
    _save_state(_session, state)
    return _ok(
        "dispatched",
        active_or_pending=active,
        limit=MERGE_MAX_PENDING_TRIGGER_CALLS,
        trigger_call_pk=getattr(call, "pk", None),
        **state,
    )


def _changed_kinds_for_node(target_dir: Path, old_hash: str | None, new_hash: str | None) -> list[str]:
    """Return which output kinds were affected between two repo hashes.

    Draft heuristic:
    - if hashes missing/invalid or equal: assume both kinds may need work;
    - otherwise inspect changed files under target_dir and map them by filename
      to memory/reflections.
    """
    if not (memgit.is_git_hash(old_hash) and memgit.is_git_hash(new_hash)):
        return ["memory", "reflections"]
    if old_hash == new_hash:
        return []

    repo = memgit.repo_for(target_dir)
    if repo is None:
        return ["memory", "reflections"]
    try:
        rel_prefix = target_dir.resolve().relative_to(repo).as_posix()
    except (OSError, ValueError):
        rel_prefix = ""

    changed = memgit.changed_paths(
        repo,
        str(old_hash),
        str(new_hash),
        rel_prefix="" if rel_prefix == "." else rel_prefix,
    )
    if not changed:
        return []

    kinds: set[str] = set()
    for rel in changed:
        name = Path(rel).name
        for kind, names in SOURCE_NAMES.items():
            if name in names:
                kinds.add(kind)
    # If nothing matched known source names, be conservative.
    return sorted(kinds) or ["memory", "reflections"]


def _build_trigger_prompt(target_dir: Path, kinds: list[str], old_hash: str | None, new_hash: str | None) -> str:
    """Build a synthesis prompt for the worker session.

    TODO: the long-running worker should probably maintain separate memory and
    reflections outputs/sessions.  This draft builds one combined message.
    """
    manifest_path = target_dir / memsources.SOURCES_FILENAME
    manifest = memsources.read_sources(manifest_path)
    node_type = str(manifest.get("type") or manifest.get("kind") or "memory")
    node_name = str(manifest.get("name") or manifest.get("key") or target_dir.name)

    sections: list[str] = [
        f"# Memory merge update\n",
        f"Target node: `{target_dir.as_posix()}`",
        f"Node type: `{node_type}`",
        f"Node name: `{node_name}`",
        f"Previous cursor hash: `{old_hash or 'unknown'}`",
        f"Latest reported hash: `{new_hash or 'unknown'}`",
        f"Affected kinds: {', '.join(kinds) if kinds else 'none'}",
        "",
        "Update the node's memory files using only the material below.",
        "Do not read source files. Do not touch .memory_sources.md or git metadata.",
        "When done, call final_result with a one-line summary.",
        "",
    ]

    for kind in kinds:
        output = KIND_OUTPUT[kind]
        # Build a pseudo item compatible with _format_sources/build_prompt helpers.
        item = {
            "manifest_path": manifest_path.as_posix(),
            "node_kind": manifest.get("kind") or "scope",
            "node_key": manifest.get("key") or "",
            "type": node_type,
            "depth": manifest.get("depth", 0),
            "sources": [
                {
                    **dict(source),
                    "last_processed_hash": old_hash or source.get("last_processed_hash"),
                    "current_hash": new_hash or source.get("current_hash"),
                }
                for source in (manifest.get("sources") or [])
                if isinstance(source, dict)
            ],
        }
        try:
            kind_prompt = build_prompt(item, kind)
        except Exception:
            kind_prompt = (
                f"## {output}\n\n"
                f"Current content:\n\n{(target_dir / output).read_text(encoding='utf-8') if (target_dir / output).exists() else '(missing)'}\n\n"
                f"Changed material:\n\n{_format_sources(list(item.get('sources') or []), target_dir, kind)}"
            )
        sections.append(f"\n---\n\n{kind_prompt}")

    return "\n".join(sections).strip() + "\n"


def trigger_merge(_session: Any) -> tuple[bool, dict[str, Any]]:
    """Merge worker task: turn latest hash into a user message.

    This is the "maybe run synthesis" step.  It should be cheap and safe to
    queue multiple times; the latest hash/cursor wins.
    """
    state = _load_state(_session)
    manifest_path = _manifest_path(state.get("manifest_path") or state.get("target_dir") or "")
    target_dir = manifest_path.parent
    if not manifest_path.exists():
        return _err(f"manifest not found: {manifest_path}", **state)

    manifest = memsources.read_sources(manifest_path)
    old_hash = state.get("last_processed_hash")
    new_hash = state.get("latest_reported_hash") or memgit.path_commit(target_dir)

    kinds = _changed_kinds_for_node(target_dir, old_hash if isinstance(old_hash, str) else None, new_hash if isinstance(new_hash, str) else None)
    if not kinds:
        state["last_action"] = "noop"
        state["last_checked_at"] = time.time()
        _save_state(_session, state)
        return _ok("noop", message="no relevant memory/reflection changes", kinds=[], **state)

    prompt = _build_trigger_prompt(target_dir, kinds, old_hash if isinstance(old_hash, str) else None, new_hash if isinstance(new_hash, str) else None)

    # Preferred path: add a user message to this same long-running worker session.
    try:
        ingest_call = _session.add_user_message(prompt, force=False, execute_turn=True)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        state["last_action"] = "error"
        state["last_error"] = str(exc)
        _save_state(_session, state)
        return _err(f"failed to enqueue ingest_user_message: {exc}", **state)

    finalize_task = _session.get_task("finalize_memory_merge")
    finalize_call_pk = None
    if finalize_task is not None:
        try:
            finalize_call = finalize_task.delay(
                ingest_call,
                target_dir=target_dir.as_posix(),
                manifest_path=manifest_path.as_posix(),
                processed_hash=new_hash,
                kinds=kinds,
            )
            finalize_call_pk = getattr(finalize_call, "pk", None)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # The synthesis message was queued; finalization can be retried.
            state["last_action"] = "finalize_schedule_error"
            state["last_error"] = str(exc)
            _save_state(_session, state)
            return _err(f"synthesis queued but finalize scheduling failed: {exc}", ingest_call_pk=getattr(ingest_call, "pk", None), **state)

    state.update({
        "last_action": "queued_synthesis",
        "last_queued_at": time.time(),
        "last_ingest_call_pk": getattr(ingest_call, "pk", None),
        "last_finalize_call_pk": finalize_call_pk,
        "pending_hash": new_hash,
        "pending_kinds": kinds,
    })
    _save_state(_session, state)
    return _ok(
        "dispatched",
        kinds=kinds,
        ingest_call_pk=getattr(ingest_call, "pk", None),
        finalize_call_pk=finalize_call_pk,
        **state,
    )


# ---------------------------------------------------------------------------
# Finalize / cursor advancement
# ---------------------------------------------------------------------------


def _result_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()[:8000]
    parts = getattr(result, "parts", None)
    if parts is None:
        return str(result).strip()[:8000]
    try:
        return "".join(str(p.to_string()) for p in parts.order_by("pk")).strip()[:8000]
    except Exception:  # pylint: disable=broad-exception-caught
        return str(result).strip()[:8000]


def finalize_memory_merge(
    _session: Any,
    synthesis_result: Any = None,
    target_dir: str = "",
    manifest_path: str = "",
    processed_hash: str | None = None,
    kinds: list[str] | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Finalize a merge worker run.

    Draft responsibilities:
    - validate output files exist / were updated;
    - commit memory repo changes;
    - record processed cursor in session-private state;
    - advance manifest source hashes when appropriate;
    - notify dispatcher/parents if node changed.

    TODO: current manifest model is node-global.  For separate memory/reflection
    workers we need per-kind cursors or a two-cursor advancement rule.
    """
    from finalize import finalize_memory

    state = _load_state(_session)
    target = _manifest_dir(target_dir or manifest_path or state.get("target_dir") or state.get("manifest_path") or "")
    manifest = _manifest_path(target)
    kinds = kinds or list(state.get("pending_kinds") or OUTPUT_FILES)
    processed_hash = (processed_hash or state.get("pending_hash") or state.get("latest_reported_hash"))

    if not target.exists():
        return _err(f"target_dir does not exist: {target}", **state)

    # Commit first so path_commit/mark_processed sees the synthesized content.
    repo = memgit.repo_for(target)
    commit_sha = None
    if repo is not None:
        try:
            commit_sha = memgit.commit_all(repo, message=f"memory: merge {target.name}")
        except Exception:  # pylint: disable=broad-exception-caught
            commit_sha = memgit.head(repo)

    # Reuse v1 validation/manifest advancement for the draft.
    ok, payload = finalize_memory(target.as_posix(), started_at=state.get("last_queued_at"))
    if not ok:
        state["last_action"] = "finalize_error"
        state["last_error"] = payload.get("message")
        _save_state(_session, state)
        return False, {**state, **payload}

    state.update({
        "last_action": "finalized",
        "last_processed_at": time.time(),
        "last_processed_hash": processed_hash,
        "last_processed_repo_head": commit_sha,
        "last_result_summary": _result_text(synthesis_result),
        "pending_hash": None,
        "pending_kinds": [],
    })
    _save_state(_session, state)

    # Draft parent notification: dispatcher can decide whether parent nodes are affected.
    # TODO: compute affected parent manifests from memory_walk/tree rather than guessing.
    parent_notification = None
    dispatcher_task = _session.get_task("memory_update_dispatcher")
    if dispatcher_task is not None:
        try:
            parent_notification = dispatcher_task.delay(target.as_posix(), commit_sha or processed_hash or "")
            parent_notification = getattr(parent_notification, "pk", None)
        except Exception:  # pylint: disable=broad-exception-caught
            parent_notification = None

    return _ok(
        "success",
        target_dir=target.as_posix(),
        manifest_path=manifest.as_posix(),
        processed_hash=processed_hash,
        repo_head=commit_sha,
        kinds=kinds,
        synthesis_result=_result_text(synthesis_result),
        parent_dispatch_call_pk=parent_notification,
        **payload,
    )
