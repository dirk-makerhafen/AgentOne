"""Dispatch layer-aware memory synthesis for pending ``.memory_sources.md`` nodes.

:func:`memory_lib.tree.walk_memory` decides *what* is stale and owns the
manifest files.  This module decides *who* consolidates it and *what they are
told*: every pending node gets a prompt tailored to its layer (task, agent, or
scope), and that prompt is sent to a fresh ``memory-manage`` subtask session.

The prompts are inlined below as ``{{token}}`` templates so they stay readable
without touching the dispatch code.  The synthesizer writes ``memory.md`` and
``reflections.md``; each spawn is immediately followed by a delayed
``memory_finalize`` call that references the child's task call, so the
framework auto-awaits the synthesizer and then advances the manifest through
:func:`memory_lib.finalize.finalize_memory`.  The LLM never edits or
advances ``.memory_sources.md``.

Layers are dispatched deepest-first: task memories before agent memories, and
agent memories before their scope.  Parents consume their children's output,
so a single pass advances one depth level; call walk + merge again until
``pending`` reaches zero.
"""

from __future__ import annotations

import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import git as memgit
import paths as mempaths
import sources as memsources


#: Shared output contract for every layer.  Appended to each layer prompt so
#: the three variants cannot drift apart on the reflections format.
REFLECTIONS_OUTPUT = '''
## Output format

Write two markdown files. No fixed schema, no YAML frontmatter, no rigid
template — use the structure that makes the content easiest to scan. Keep it
compact and factual.

`memory.md` is durable knowledge: what is true, what was decided, what to know.

`reflections.md` is consolidated reflection: what was learned, what worked,
what failed, what to do differently, and patterns worth carrying upstream.
Merge lower-level reflections into higher-level signal; do not just
concatenate. Prefer concrete observations over generic advice. When useful,
include short evidence pointers (session/report names, dates, file paths), but
do not pad the file with provenance.

Good reflections are specific and actionable, for example:

- "Ran the same update 12+ times with identical prompt; this is expected batch
  behavior, not a failure."
- "git commit after a batch sometimes reports clean because the prior turn
  already committed; check git status before committing."
- "Legacy indexes often miss entity arrays; populate persons/companies/products
  from source summaries instead of leaving them empty."

Drop stale, duplicated, or superseded observations. The newest confirmed truth
wins when sources conflict.
'''


AGENT_PROMPT = '''
# Agent memory synthesis

You are the memory synthesizer for agent **{{node_label}}**
({{scope_description}}). Roll the task-level memories up into this agent's
durable memory.

Target directory: `{{target_dir}}`

## Changed since the last synthesis

{{changed_sources}}

## Read

Each direct sub-directory of `{{target_dir}}/tasks/` is one task this agent
works on. Its `memory.md` holds task knowledge and its `reflections.md` holds
consolidated lessons about doing that task.

- Read the changed task memories first, then skim the rest for context.
- Leave task-specific detail where it is; promote only what matters across
  tasks or is useful upstream.
- Treat this agent's existing `memory.md` and `reflections.md` as the baseline
  you are updating, not as the only truth.

## Write

`{{target_dir}}/memory.md` — durable knowledge about this agent's domain:

- what this agent is responsible for and the systems it touches
- settled decisions, conventions, and boundaries that apply across its tasks
- environment and tooling facts the next agent would otherwise rediscover
- recurring traps and how to avoid them

`{{target_dir}}/reflections.md` — consolidated reflection for this agent.

- patterns that repeatedly succeed
- mistakes that keep recurring and their fix
- delegation habits and sequencing that worked
- user preferences that apply across its tasks
- ideas for skills, tools, scripts, or harness fixes, when evidence supports them

## Rules

- Synthesize, do not concatenate. Merge new facts into the existing files and
  drop stale or superseded detail; the newest truth wins.
- A reader with no access to the task memories must understand the result.
  Keep it self-contained.
- Never invent information. If sources conflict, prefer the newer one and say
  so when it matters.
- Keep each file under ~8000 characters. If files get longer, compact them and
  keep the most important content.
- Only read and write inside `{{target_dir}}`. Never touch
  `.memory_sources.md`, git metadata, or other memory levels.
- The harness marks this node processed when your session ends. Do not advance
  the manifest yourself: write both files, call `final_result` with a one-line
  summary, and stop.
''' + REFLECTIONS_OUTPUT
SCOPE_PROMPT = '''
# Scope memory synthesis

You are the memory synthesizer for {{scope_description}}.

Target directory: `{{target_dir}}`

## Changed since the last synthesis

{{changed_sources}}

## Read

- `{{target_dir}}/agents/*/memory.md` and `reflections.md` — what each agent in
  this scope has learned.
- Child scopes: {{child_scopes}}. Their own `memory.md` and `reflections.md`
  already summarize everything below them — do not re-read their raw reports.

Start with the changed material above, then read the rest to keep the summary
coherent. Treat this scope's existing `memory.md` and `reflections.md` as the
baseline you are updating, not as the only truth.

## Write

`{{target_dir}}/memory.md` — the shared picture for this scope:

- goals, architecture, and the parts of the system this scope owns
- environment, tooling, and setup facts worth remembering
- conventions and decisions that hold across agents and child scopes
- relationships between child scopes and where responsibility sits

`{{target_dir}}/reflections.md` — consolidated cross-agent reflection for this scope:

- coordination patterns that work (and the ones that do not)
- recurring failures and their fixes
- preferences that should shape how work is done here
- what to check first when something in this scope breaks
- missing capabilities or harness issues worth surfacing upstream

## Rules

- Synthesize, do not concatenate. Merge new facts into the existing files and
  drop stale or superseded detail; the newest truth wins.
- A reader new to this scope must understand the result without opening agent
  or session memories. Keep it self-contained.
- Never invent information. If sources conflict, prefer the newer one and say
  so when it matters.
- Keep each file under ~8000 characters. Prune rather than spill over.
- Only read and write inside `{{target_dir}}` and its child scope directories.
  Never touch `.memory_sources.md`, git metadata, or files above this scope.
- The harness marks this node processed when your session ends. Do not advance
  the manifest yourself: write both files, call `final_result` with a one-line
  summary, and stop.
''' + REFLECTIONS_OUTPUT
TASK_PROMPT = '''
# Task memory synthesis

You are the memory synthesizer for one task. Consolidate the session reports of
task **{{node_label}}** ({{scope_description}}) into memory that the next agent
can act on.

Target directory: `{{target_dir}}`

## Changed since the last synthesis

{{changed_sources}}

## Read

The task's reports live under `{{target_dir}}/sessions/`:

- `reflections_*.md` — what the agent learned while doing this work: mistakes,
  corrections, preferences, and shortcuts worth repeating.
- `compaction_*.md` — what happened in each session: goals, decisions,
  outcomes, dead ends, and open threads.

Start with the changed material above, then read older reports only when you
need context. Treat the existing `memory.md` and `reflections.md` as the
baseline you are updating, not as the only truth.

## Write

`{{target_dir}}/memory.md` — what the next agent must know to work this task
well:

- what the task is for, its inputs and outputs, and its recurring constraints
- decisions that were made and why, plus conventions that are now settled
- environment specifics, gotchas, and approaches that failed
- open threads and how they were resolved (or what is still pending)

`{{target_dir}}/reflections.md` — consolidated reflection for this task.

- recurring mistakes and the fix that worked
- patterns and shortcuts worth reusing
- user feedback and preferences that should shape future runs
- ideas for skills, tools, scripts, or harness fixes, when evidence supports them

## Rules

- Synthesize, do not concatenate. Merge new facts into the existing files and
  drop stale or superseded detail; the newest truth wins.
- A reader with no access to the reports must understand the result. Keep it
  self-contained.
- Never invent information. If reports conflict, prefer the newer one and say
  so when it matters.
- Keep each file under ~8000 characters. Prune rather than spill over.
- Only read and write inside `{{target_dir}}`. Never touch
  `.memory_sources.md`, git metadata, or other memory levels.
- The harness marks this node processed when your session ends. Do not advance
  the manifest yourself: write both files, call `final_result` with a one-line
  summary, and stop.
''' + REFLECTIONS_OUTPUT

_PROMPTS = {
    "task": TASK_PROMPT,
    "agent": AGENT_PROMPT,
    "scope": SCOPE_PROMPT,
}
_SCOPE_KINDS = ("global", "project", "workspace")
_LAYER_ORDER = {"task": 0, "agent": 1, "scope": 2}
_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

#: A node whose marker is newer than this is considered abandoned and may be
#: dispatched again even if its synthesizer session still looks active.
INFLIGHT_TTL_SECONDS = 60 * 60

#: How many individual file names to list per source in the prompt.
MAX_LISTED_FILES = 8


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _layer_hint(item: dict[str, Any]) -> str:
    """Return ``task`` / ``agent`` / ``scope`` from the walker's item fields."""
    kind = str(item.get("node_kind") or "").strip().lower()
    if kind in _LAYER_ORDER:
        return kind
    if kind in _SCOPE_KINDS:
        return "scope"

    node_type = str(item.get("type") or "").strip().lower()
    if node_type.endswith("-agent-task") or node_type.endswith("-task"):
        return "task"
    if node_type.endswith("-agent"):
        return "agent"
    return "scope"


def _classify(
    item: dict[str, Any], manifest: dict[str, Any]
) -> tuple[str, str]:
    """Return ``(layer, scope_kind)`` for a node, preferring its manifest."""
    kind = str(manifest.get("kind") or item.get("node_kind") or "").strip().lower()
    node_type = str(manifest.get("type") or item.get("type") or "").strip().lower()

    if kind == "task" or node_type.endswith("-agent-task"):
        layer = "task"
    elif kind == "agent" or node_type.endswith("-agent"):
        layer = "agent"
    elif kind in _SCOPE_KINDS or node_type in _SCOPE_KINDS:
        layer = "scope"
    else:
        raise ValueError(
            f"cannot classify memory node {item.get('manifest_path')!r} "
            f"(kind={kind!r}, type={node_type!r})"
        )

    scope = next(
        (
            candidate
            for candidate in _SCOPE_KINDS
            if node_type == candidate or node_type.startswith(candidate + "-")
        ),
        "",
    )
    if layer == "scope" and kind in _SCOPE_KINDS:
        scope = kind
    return layer, scope or "global"


def _node_label(
    item: dict[str, Any], manifest: dict[str, Any], layer: str, scope: str
) -> str:
    """Return a human-readable label for the node being synthesized."""
    name = str(manifest.get("name") or "").strip()
    key = str(item.get("node_key") or "").strip()

    if layer == "task":
        label = key or name.removeprefix("task_")
        return label or "default"
    if layer == "agent":
        return name or key or "unknown"
    return name or key or scope


def _scope_description(scope: str, label: str) -> str:
    """Describe the scope in the terms a synthesizer needs."""
    if scope == "project":
        return (
            f"the **{label}** project scope "
            "(every workspace and agent owned by that project)"
        )
    if scope == "workspace":
        return (
            f"the **{label}** workspace scope "
            "(this codebase and the agents working in it)"
        )
    return "the instance-wide (global) scope"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _source_label(source: dict[str, Any]) -> str:
    """Return a readable description of one changed source entry."""
    node_type = str(source.get("type") or "").strip().lower()
    path = str(source.get("path") or "").strip()
    suffix = path.rstrip("/").rsplit("/", 1)[-1]

    if node_type in _SCOPE_KINDS:
        return f"child {node_type} memory"
    if suffix == "agents":
        return "agent memory in this scope"
    if suffix == "tasks":
        return "task memory for this agent"
    if suffix == "sessions":
        return "session reports (reflections and compactions)"
    return node_type or "memory source"


def _source_dir(source: dict[str, Any], target_dir: Path) -> Path | None:
    """Resolve a manifest source path against the node's directory."""
    raw = str(source.get("path") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = target_dir / path
    return path


def _relative_label(path: Path, base: Path) -> str:
    """Return *path* relative to *base* for prompt display."""
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except (OSError, ValueError):
        return path.name


def _git_changed_paths(source_dir: Path, source: dict[str, Any]) -> list[str] | None:
    """Return files changed between the source's two commits, if possible."""
    old = source.get("last_processed_hash")
    new = source.get("current_hash")
    if not (memgit.is_git_hash(old) and memgit.is_git_hash(new)) or old == new:
        return None

    repo = memgit.repo_for(source_dir)
    if repo is None:
        return None
    try:
        rel_prefix = source_dir.resolve().relative_to(repo).as_posix()
    except (OSError, ValueError):
        rel_prefix = ""

    return [
        _relative_label(repo / rel_path, source_dir)
        for rel_path in memgit.changed_paths(
            repo, str(old), str(new), rel_prefix="" if rel_prefix == "." else rel_prefix
        )
    ]


def _walk_source_files(source_dir: Path) -> list[str]:
    """List every content file below *source_dir*, sorted by path."""
    try:
        files = [
            path
            for path in source_dir.rglob("*")
            if path.is_file() and not memsources.is_metadata_path(path)
        ]
    except OSError:
        return []
    return sorted(_relative_label(path, source_dir) for path in files)


def _source_files(
    source: dict[str, Any], target_dir: Path
) -> tuple[bool, list[str], int]:
    """Return ``(from_git_range, listed_files, total_files)`` for a source."""
    source_dir = _source_dir(source, target_dir)
    if source_dir is None:
        return False, [], 0

    changed = _git_changed_paths(source_dir, source)
    if changed is not None:
        names = [
            name
            for name in changed
            if not memsources.is_metadata_path(source_dir / name)
        ]
        return True, names[:MAX_LISTED_FILES], len(names)

    names = _walk_source_files(source_dir)
    return False, names[:MAX_LISTED_FILES], len(names)


def _format_sources(sources: list[dict[str, Any]], target_dir: Path) -> str:
    """Format the walker's changed-source entries as a short bullet list."""
    if not sources:
        return "_No source changes were reported._"

    lines: list[str] = []
    for source in sources:
        path = str(source.get("path") or "?")
        parts = [f"- `{path}` — {_source_label(source)}"]

        changed = source.get("changed_chars")
        if changed:
            parts.append(f"{int(changed):,} chars changed")

        hours = source.get("hours_since_processed")
        if isinstance(hours, (int, float)) and hours > 0:
            parts.append(f"last synthesized {hours:g}h ago")

        last = str(source.get("last_processed_hash") or "")[:8] or "never"
        current = str(source.get("current_hash") or "")[:8] or "missing"
        parts.append(f"{last} → {current}")

        lines.append("  ".join(parts))

        from_git_range, listed, total = _source_files(source, target_dir)
        if listed:
            label = "Changed files" if from_git_range else "Files"
            rendered = ", ".join(f"`{name}`" for name in listed)
            if total > len(listed):
                rendered += f" (+{total - len(listed)} more)"
            lines.append(f"  {label}: {rendered}")

    return "\n".join(lines)


def _child_scopes(sources: list[dict[str, Any]]) -> str:
    """Return a readable list of child scope directories, if any."""
    children = [
        source
        for source in sources
        if str(source.get("type") or "").strip().lower() in _SCOPE_KINDS
    ]
    if not children:
        return "none"
    return ", ".join(
        f"`{source.get('path')}` ({source.get('type')})" for source in children
    )


def _render(template: str, values: dict[str, Any]) -> str:
    """Replace ``{{token}}`` placeholders, failing loudly on a missing token."""
    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"prompt token {{{{{key}}}}} has no value")
        return str(values[key])

    return _TOKEN_RE.sub(substitute, template).strip() + "\n"


def build_prompt(item: dict[str, Any]) -> str:
    """Build the layer-specific synthesis prompt for one pending node.

    Args:
        item: One entry from ``walk_memory()["needs_update"]``.  It must
            contain ``manifest_path``, ``node_kind``, ``node_key``, ``type``,
            and ``sources``.

    Returns:
        The rendered prompt, ready to send to a ``memory-manage`` session.

    Raises:
        ValueError: If the node cannot be classified or its manifest is
            missing.
        KeyError: If a template references an unknown placeholder.
    """
    manifest_path = str(item.get("manifest_path") or "")
    if not manifest_path:
        raise ValueError("memory item has no manifest_path")

    manifest_file = Path(manifest_path).expanduser()
    if not manifest_file.is_file():
        raise ValueError(f"memory manifest not found: {manifest_file}")

    manifest = memsources.read_sources(manifest_file)
    layer, scope = _classify(item, manifest)
    sources = list(item.get("sources") or [])

    label = _node_label(item, manifest, layer, scope)
    target_dir = manifest_file.parent.resolve().as_posix()

    return _render(
        _PROMPTS[layer],
        {
            "level": layer,
            "node_label": label,
            "scope_description": _scope_description(scope, label),
            "target_dir": target_dir,
            "changed_sources": _format_sources(sources, manifest_file.parent),
            "child_scopes": _child_scopes(sources),
        },
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _item_target_dir(item: dict[str, Any]) -> Path:
    """Return the resolved target directory for a walker item."""
    manifest_path = Path(str(item.get("manifest_path") or ""))
    return manifest_path.parent.resolve()


def _is_descendant(child_dir: Path, parent_dir: Path) -> bool:
    """Return True when *child_dir* is inside *parent_dir*."""
    if child_dir == parent_dir:
        return False
    try:
        child_dir.relative_to(parent_dir)
        return True
    except ValueError:
        return False


def _select_batch(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Return pending nodes ready to synthesize, across levels.

    A node is ready when no other pending node is its descendant (children must
    be synthesized before parents consume them). Ready nodes are prioritized
    deepest-first so we unblock parents quickly, then fill remaining capacity
    with ready higher-level nodes.
    """
    if not items:
        return []

    pending_dirs = [_item_target_dir(item) for item in items]
    ready: list[dict[str, Any]] = []
    for item, item_dir in zip(items, pending_dirs):
        blocked = any(
            _is_descendant(other_dir, item_dir)
            for other_dir in pending_dirs
            if other_dir != item_dir
        )
        if not blocked:
            ready.append(item)

    # Deepest-first, stable within same depth/layer.
    ready.sort(
        key=lambda item: (
            -int(item["depth"]) if isinstance(item.get("depth"), int) else -_LAYER_ORDER.get(_layer_hint(item), 0),
        )
    )

    if limit and limit > 0:
        ready = ready[:limit]
    return ready


def _display_target(path: Path) -> str:
    """Return a readable name for a node directory."""
    return path.parent.name if path.name == "memory" else path.name


def _read_inflight(target_dir: Path) -> dict[str, Any]:
    """Return the node's in-flight marker payload (empty when absent)."""
    try:
        data = json.loads(
            mempaths.inflight_path(target_dir).read_text(encoding="utf-8")
        )
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _inflight_active(target_dir: Path) -> bool:
    """Return whether another synthesis is still running for *target_dir*."""
    data = _read_inflight(target_dir)
    if not data:
        return False

    try:
        started = float(data.get("started_at") or 0)
    except (TypeError, ValueError):
        started = 0
    if started <= 0 or (time.time() - started) > INFLIGHT_TTL_SECONDS:
        return False

    session_pk = data.get("session_pk")
    if not isinstance(session_pk, int):
        return True
    try:
        from server.models.sessions.session import SessionModel

        return SessionModel.objects.filter(pk=session_pk, is_active=True).exists()
    except Exception:  # pylint: disable=broad-exception-caught
        return True


def _write_inflight(
    target_dir: Path, session_pk: int, layer: str, started_at: float | None = None
) -> None:
    """Record that *target_dir* is being synthesized by *session_pk*."""
    payload = {
        "session_pk": session_pk,
        "layer": layer,
        "started_at": started_at if started_at is not None else time.time(),
    }
    try:
        mempaths.inflight_path(target_dir).write_text(
            json.dumps(payload) + "\n", encoding="utf-8"
        )
    except OSError:
        pass


def _clear_inflight(target_dir: Path) -> None:
    """Remove the node's in-flight marker (best effort)."""
    try:
        mempaths.inflight_path(target_dir).unlink(missing_ok=True)
    except OSError:
        pass


def _scope_source_dirs(target_dir: Path) -> list[Path]:
    """Return child scope directories listed in the node's manifest."""
    manifest = memsources.read_sources(target_dir / memsources.SOURCES_FILENAME)
    found: list[Path] = []
    for source in manifest.get("sources") or []:
        kind = str(source.get("type") or "").strip().lower()
        if kind not in _SCOPE_KINDS:
            continue
        raw = str(source.get("path") or "").strip()
        if not raw:
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = target_dir / path
        found.append(path.resolve())
    return found


def _allow_patterns(roots: list[Path]) -> list[str]:
    """Return exact + recursive allow globs for *roots*."""
    patterns: list[str] = []
    for root in roots:
        posix = root.as_posix()
        for pattern in (posix, f"{posix}/**"):
            if pattern not in patterns:
                patterns.append(pattern)
    return patterns


def _relative_allow_patterns(
    roots: list[Path], workspace_root: Path | None
) -> list[str]:
    """Return workspace-relative allow globs for the roots inside *workspace_root*."""
    if workspace_root is None:
        return []
    patterns: list[str] = []
    for root in roots:
        try:
            rel = root.relative_to(workspace_root).as_posix()
        except ValueError:
            continue
        if rel in ("", "."):
            continue
        for pattern in (rel, f"{rel}/**"):
            if pattern not in patterns:
                patterns.append(pattern)
    return patterns


def _access_overrides(session: Any, target_dir: Path) -> dict[str, Any]:
    """Return a session ``access`` block granting this synthesizer its node.

    Memory nodes live in their own scope's ``.agentone/memory`` tree, which is
    usually outside the spawning session's workspace.  The child gets write
    access to the node and read access to the node plus its child scopes (a
    scope synthesizer consumes them).  Absolute globs cover external nodes;
    workspace-relative copies cover nodes inside a read-only workspace.
    """
    write_roots = [target_dir.resolve()]
    read_roots = write_roots + _scope_source_dirs(target_dir)

    workspace_path = getattr(getattr(session, "workspace", None), "path", None)
    workspace_root = Path(workspace_path).resolve() if workspace_path else None

    access: dict[str, Any] = {
        "external": {
            "read": {"default": "deny", "allow": _allow_patterns(read_roots)},
            "write": {"default": "deny", "allow": _allow_patterns(write_roots)},
        }
    }
    rel_read = _relative_allow_patterns(read_roots, workspace_root)
    rel_write = _relative_allow_patterns(write_roots, workspace_root)
    if read_roots or write_roots:
        # Absolute copies matter too: a memory node under the workspace's
        # manifest dir (e.g. ``~/.agentone/workspaces/x/memory``) counts as
        # "inside" the policy but is not under the workspace *path*, so no
        # workspace-relative pattern can reach it.
        access["workspace"] = {
            "read": {
                "allow": list(dict.fromkeys(rel_read + _allow_patterns(read_roots)))
            },
            "write": {
                "allow": list(dict.fromkeys(rel_write + _allow_patterns(write_roots)))
            },
        }
    return access


def _spawn_synthesizer(
    _session: Any, layer: str, target_dir: Path, prompt: str
) -> dict[str, Any]:
    """Spawn one ``memory-manage`` subtask and chain finalization after it.

    The child is a single-use ``SUBTASK_DELEGATE`` session.  Its task call is
    handed to ``memory_finalize`` as an argument, which parks that call in
    ``WAITING_DEPENDENCY``: the framework auto-awaits the synthesizer and then
    invokes ``memory_finalize`` with its ``final_result`` message.  Neither this
    tool nor the LLM advances the manifest.
    """
    from server.models.enums.session_enums import SessionType

    finalize_task = _session.get_task("memory_finalize")
    if finalize_task is None:
        return {
            "status": "error",
            "error": "task 'memory_finalize' is not available to this session",
        }

    started_at = time.time()
    child = _session.spawn_subagent(
        "memory-manage",
        name=f"memory:{layer}:{uuid.uuid4().hex[:12]}",
        description=f"{layer} memory: {_display_target(target_dir)}",
        session_type=SessionType.SUBTASK_DELEGATE,
        group_key=f"memory:{layer}",
        allow_internal=True,
        access=_access_overrides(_session, target_dir),
    )
    if child is None:
        return {"status": "error", "error": "agent 'memory-manage' not found"}

    _write_inflight(target_dir, child.model.pk, layer, started_at)
    try:
        synthesizer_call = child.add_user_message(prompt)
        finalize_call = finalize_task.delay(
            synthesizer_call,
            target_dir=target_dir.resolve().as_posix(),
            started_at=started_at,
        )
    except Exception:
        _clear_inflight(target_dir)
        raise

    return {
        "status": "dispatched",
        "session_pk": child.model.pk,
        "finalize_call_pk": getattr(finalize_call, "pk", None),
        "finalize": finalize_call,
    }


def memory_merge_item(_session: Any, item: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Synthesize one pending memory node (map worker).

    Dispatches one synthesizer subtask and chains ``memory_finalize``. The
    returned ``finalize`` ref lets the scheduler wait for the full subgraph.
    """
    manifest_path = Path(str(item.get("manifest_path") or ""))
    target_dir = _item_target_dir(item)
    layer = _layer_hint(item)
    outcome: dict[str, Any] = {
        "manifest": manifest_path.as_posix(),
        "target_dir": target_dir.as_posix(),
        "layer": layer,
    }

    if _inflight_active(target_dir):
        return True, {
            **outcome,
            "status": "skipped",
            "reason": "synthesis already running",
        }

    try:
        prompt = build_prompt(item)
        spawn = _spawn_synthesizer(_session, layer, target_dir, prompt)
        outcome.update(spawn)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {**outcome, "status": "error", "error": str(exc)}

    if outcome.get("status") == "dispatched":
        return True, outcome
    return False, outcome


def merge_items(
    _session: Any,
    items: list[dict[str, Any]],
    limit: int = 0,
) -> tuple[bool, dict[str, Any]]:
    """Dispatch ready pending nodes via ``map`` (pipeline).

    Selects nodes whose descendants are not pending, deepest-first, then
    dispatches them as ``memory_merge_item`` map tasks. Ready nodes can span
    levels, so higher-level nodes may be synthesized in the same batch when
    their children are not pending.
    """
    try:
        batch = _select_batch(list(items), int(limit or 0))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"status": "error", "message": str(exc)}

    layers = sorted({_layer_hint(item) for item in batch}, key=lambda l: _LAYER_ORDER.get(l, 99))
    layer = layers[0] if len(layers) == 1 else ("mixed" if layers else None)

    if not batch:
        return True, {
            "status": "success",
            "layer": None,
            "dispatched": [],
            "skipped": [],
            "failed": [],
            "items": [],
            "results": [],
            "remaining": 0,
            "message": "Nothing to synthesize.",
        }

    map_task = _session.get_task("map")
    try:
        from runtime.tasks.bound_task import BoundTask

        has_map = isinstance(map_task, BoundTask)
    except Exception:  # pylint: disable=broad-exception-caught
        has_map = map_task is not None and hasattr(map_task, "delay")
    if not has_map:
        # Fallback: direct dispatch (keeps behavior in restricted sessions/tests).
        dispatched: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for item in batch:
            _ok, outcome = memory_merge_item(_session, item)
            status = outcome.get("status")
            if status == "dispatched":
                dispatched.append(outcome)
            elif status == "skipped":
                skipped.append(outcome)
            else:
                failed.append(outcome)
        success = bool(dispatched) or (bool(skipped) and not failed)
        if dispatched:
            status = "success"
        elif skipped and not failed:
            status = "busy"
        else:
            status = "error"
        return success, {
            "status": status,
            "layer": layer,
            "dispatched": dispatched,
            "skipped": skipped,
            "failed": failed,
            "items": [str(it.get("manifest_path") or "") for it in batch],
            "results": [],
            "remaining": max(0, len(items) - len(dispatched) - len(skipped)),
        }

    # Ready nodes are independent (no pending descendant). Keep map
    # concurrency sequential by default because each item spawns a synthesizer
    # subtask and a finalize chain.
    results = map_task.delay(
        target="memory_merge_item",
        list_of_kwargs=[{"item": item} for item in batch],
        concurrency=1,
    )
    return True, {
        "status": "success",
        "layer": layer,
        "dispatched": [
            {
                "manifest": str(it.get("manifest_path") or ""),
                "target_dir": _item_target_dir(it).as_posix(),
                "status": "dispatched",
                "layer": _layer_hint(it),
            }
            for it in batch
        ],
        "skipped": [],
        "failed": [],
        "items": [str(it.get("manifest_path") or "") for it in batch],
        "results": results,
        "remaining": max(0, len(items) - len(batch)),
    }


def memory_merge(
    _session: Any,
    limit: int = 1,
) -> tuple[bool, dict[str, Any]]:
    """Delegate pending memory nodes to synthesizer sessions via a pipeline.

    Walks the memory tree, selects ready nodes (no pending descendant), and
    dispatches them as ``memory_merge_item`` map tasks. Ready nodes can span
    levels, so a higher-level node may be synthesized in the same batch when
    its children are not pending. Each item spawns a synthesizer subtask and
    chains ``memory_finalize``; returning map results makes the caller wait for
    the full subgraph.

    Args:
        _session: The calling session (bound automatically).
        limit: Maximum number of ready nodes to dispatch in this call. ``0``
            dispatches all ready nodes.

    Returns:
        ``(True, {"status": "success", "dispatched": int, "items": [...],
        "results": [...], "remaining": int})`` or ``(False, {...})`` on error.
    """
    try:
        items = _walk_pending()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"status": "error", "message": str(exc)}

    return merge_items(_session, items, limit)


def _walk_pending() -> list[dict[str, Any]]:
    """Re-walk the memory tree and return its ``needs_update`` list."""
    from tree import walk_memory

    summary = walk_memory(write=True, refresh=False)
    return list(summary.get("needs_update") or [])
