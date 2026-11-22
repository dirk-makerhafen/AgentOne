"""Dispatch layer-aware memory synthesis for pending ``.memory_sources.md`` nodes.

``tree.walk_memory`` decides *what* is stale and owns the manifest files.  This
module decides *who* consolidates it and *what they are told*.

Every pending node gets **two** small, independent synthesizer sessions: one
rewrites ``memory.md``, the other rewrites ``reflections.md``.  They run in
parallel and the framework auto-awaits both task calls before ``memory_finalize``
advances the manifest.  The LLM never edits or advances ``.memory_sources.md``.

To keep those sessions short, source files are never listed for the agent to go
read.  The changed material is inlined instead — a unified diff when that is
shorter than the replacement text, otherwise the full text.  Tool access is
narrowed to a single edit tool plus ``grep`` on the one output file.

Layers are dispatched deepest-first: task memories before agent memories, and
agent memories before their scope.  Parents consume their children's output, so
a single pass advances one depth level; call walk + merge again until
``pending`` reaches zero.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

import git as memgit
import paths as mempaths
import sources as memsources


MEMORY_OUTPUT = "memory.md"
REFLECTIONS_OUTPUT = "reflections.md"
OUTPUT_FILES = (MEMORY_OUTPUT, REFLECTIONS_OUTPUT)

#: Which synthesizer owns which output, and which source filenames it consumes.
KIND_OUTPUT = {
    "memory": MEMORY_OUTPUT,
    "reflections": REFLECTIONS_OUTPUT,
}
SOURCE_NAMES = {
    "memory": frozenset({"compaction.md", MEMORY_OUTPUT}),
    "reflections": frozenset({REFLECTIONS_OUTPUT}),
}

#: Inlined-context budget.  Source material is truncated per file and in total
#: so a synthesizer cannot be dragged into a long exploratory session.
MAX_SOURCE_FILE_CHARS = 4000
MAX_SOURCE_TOTAL_CHARS = 12000

#: Above this size a size note (never a number) is injected into the prompt.
LARGE_OUTPUT_CHARS = 8000

#: Tools left available to a synthesizer.  Everything else is denied so the
#: agent edits one file from the inlined context and finishes.
SYNTHESIZER_DISALLOWED_TOOLS = [
    "core.load_skill",
    "memory.*",
    "filesystem-read.read",
    "filesystem-read.glob",
    "filesystem-read.tree",
    "filesystem-read.stat",
    "filesystem-read.diff",
    "filesystem-read.read_image",
    "filesystem-write.append",
    "filesystem-write.copy",
    "filesystem-write.mkdir",
    "filesystem-write.move",
    "filesystem-write.rm",
    "filesystem-write.write",
]
SYNTHESIZER_DISALLOWED_TASKS = ["compact.*", "memory_finalize"]

#: Hard call-time gate.  The LLM only ever needs to edit one file, optionally
#: grep it, and return a summary.  Any other tool attempt aborts the session
#: instead of sending it into an exploratory loop.  ``final_result`` is a tool
#: (not a task), so it must be listed here for the synthesizer to report back.
SYNTHESIZER_TOOL_ALLOWLIST = ["edit", "multiedit", "grep", "final_result"]
SYNTHESIZER_MAX_TURNS = 10

_LAYER_TITLES = {
    "task": "Task memory synthesis",
    "agent": "Agent memory synthesis",
    "scope": "Scope memory synthesis",
}

_LAYER_GUIDANCE = {
    ("task", "memory"): """Durable knowledge about doing this task:

- what the task is for, its inputs and outputs, and its recurring constraints
- decisions that were made and why, plus conventions that are now settled
- environment specifics, gotchas, and approaches that failed
- open threads and how they were resolved (or what is still pending)""",
    ("task", "reflections"): """Consolidated reflection for this task:

- recurring mistakes and the fix that worked
- patterns and shortcuts worth reusing
- user feedback and preferences that should shape future runs
- ideas for skills, tools, scripts, or harness fixes, when evidence supports them""",
    ("agent", "memory"): """Durable knowledge about this agent's domain:

- what this agent is responsible for and the systems it touches
- settled decisions, conventions, and boundaries that apply across its tasks
- environment and tooling facts the next agent would otherwise rediscover
- recurring traps and how to avoid them""",
    ("agent", "reflections"): """Consolidated reflection for this agent:

- patterns that repeatedly succeed
- mistakes that keep recurring and their fix
- delegation habits and sequencing that worked
- user preferences that apply across its tasks
- ideas for skills, tools, scripts, or harness fixes, when evidence supports them""",
    ("scope", "memory"): """The shared picture for this scope:

- goals, architecture, and the parts of the system this scope owns
- environment, tooling, and setup facts worth remembering
- conventions and decisions that hold across agents and child scopes
- relationships between child scopes and where responsibility sits""",
    ("scope", "reflections"): """Consolidated cross-agent reflection for this scope:

- coordination patterns that work (and the ones that do not)
- recurring failures and their fixes
- preferences that should shape how work is done here
- what to check first when something in this scope breaks
- missing capabilities or harness issues worth surfacing upstream""",
}

SYNTHESIS_PROMPT = '''# {{title}} — {{output_name}}

You are updating **{{output_name}}** for {{node_label}} ({{scope_description}}).
Target directory: `{{target_dir}}`

## Current `{{output_name}}`

{{current_content}}

## Changed material

Already inlined below: a short diff when that is smaller than the replacement
text, otherwise the new content verbatim. Do not open or read any source file —
everything you need is here.

{{changed_sources}}

{{size_note}}## Write

Update **`{{target_dir}}/{{output_name}}`** only.

{{guidance}}

## Rules

- Synthesize, do not concatenate. Merge the new material into the existing
  content and drop stale, duplicated, or superseded entries. The newest
  confirmed truth wins.
- A reader with no access to the reports must understand the result. Keep it
  self-contained, compact, and factual. No YAML frontmatter, no fixed schema.
- Never invent information. If sources conflict, prefer the newer one.
- Write the file even when you decide it needs no changes, then call
  `final_result` with a one-line summary and stop. The harness finalizes the
  node once both synthesizers finish; do not advance the manifest yourself or
  touch git metadata.
'''

SIZE_NOTE = '''## Size note

This file is getting relatively large. Prune stale, duplicated, or superseded
entries. If related material is not HOT — not needed in the next few steps but
still worth remembering — move it into its own file in this directory and add a
short relative link to it from `{{output_name}}`.

'''

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

_SCOPE_KINDS = ("global", "project", "workspace")
_LAYER_ORDER = {"task": 0, "agent": 1, "scope": 2}
_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

#: A node whose marker is newer than this is considered abandoned and may be
#: dispatched again even if its synthesizer session still looks active.
INFLIGHT_TTL_SECONDS = 60 * 60


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


def _scope_description(scope: str, label: str, layer: str = "scope") -> str:
    """Describe the node in terms a synthesizer needs.

    Task and agent nodes have their own label; calling them a "project scope"
    would be misleading because the label is a task key or agent name, not a
    project name.  Scope nodes use the named scope description.
    """
    if layer == "task":
        return f"task `{label}`"
    if layer == "agent":
        return f"agent `{label}`"
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
# Inlined source material
# ---------------------------------------------------------------------------


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


def _repo_relative(repo: Path, source_dir: Path, rel_name: str) -> str:
    """Return *rel_name* (relative to *source_dir*) relative to *repo*."""
    try:
        prefix = source_dir.resolve().relative_to(repo).as_posix()
    except (OSError, ValueError):
        prefix = ""
    full = f"{prefix}/{rel_name}" if prefix and prefix != "." else rel_name
    return full.lstrip("/")


def _recency_key(source_dir: Path, rel_name: str) -> tuple[int, float, str]:
    """Order source files newest-first (session pk, then mtime, then name)."""
    path = source_dir / rel_name
    session_part = Path(rel_name).parts[0] if Path(rel_name).parts else ""
    try:
        session_pk = int(session_part)
    except ValueError:
        session_pk = 0
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (session_pk, mtime, rel_name)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n… [truncated]"


def _source_payloads(
    sources: list[dict[str, Any]], target_dir: Path, kind: str
) -> list[dict[str, str]]:
    """Collect the relevant changed files with short full-text or diff bodies."""
    wanted = SOURCE_NAMES[kind]
    payloads: list[dict[str, str]] = []

    for source in sources:
        source_dir = _source_dir(source, target_dir)
        if source_dir is None or not source_dir.is_dir():
            continue

        old = source.get("last_processed_hash")
        new = source.get("current_hash")
        valid_hashes = (
            memgit.is_git_hash(old)
            and memgit.is_git_hash(new)
            and old != new
        )
        repo = memgit.repo_for(source_dir) if valid_hashes else None
        changed = _git_changed_paths(source_dir, source) if repo else None
        names = changed if changed is not None else _walk_source_files(source_dir)

        for rel_name in names:
            if Path(rel_name).name not in wanted:
                continue
            path = source_dir / rel_name
            try:
                body = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue

            repo_rel = _repo_relative(repo, source_dir, rel_name) if repo else ""
            diff = (
                memgit.diff_file(repo, str(old), str(new), repo_rel)
                if repo and repo_rel
                else None
            )
            if diff and len(diff) < len(body):
                rendered = _truncate(diff, MAX_SOURCE_FILE_CHARS)
                form = "diff since last synthesis"
            else:
                rendered = _truncate(body, MAX_SOURCE_FILE_CHARS)
                form = "full content"
            payloads.append({
                "label": rel_name,
                "form": form,
                "body": rendered,
                "sort": _recency_key(source_dir, rel_name),  # type: ignore[dict-item]
            })

    payloads.sort(key=lambda item: item["sort"], reverse=True)  # type: ignore[arg-type]

    selected: list[dict[str, str]] = []
    used = 0
    for payload in payloads:
        body = payload["body"]
        if used + len(body) > MAX_SOURCE_TOTAL_CHARS:
            remaining = MAX_SOURCE_TOTAL_CHARS - used
            if remaining <= 80:
                break
            body = _truncate(body, remaining)
            used = MAX_SOURCE_TOTAL_CHARS
        else:
            used += len(body)
        selected.append({**payload, "body": body})
        if used >= MAX_SOURCE_TOTAL_CHARS:
            break
    return selected


def _format_sources(
    sources: list[dict[str, Any]], target_dir: Path, kind: str
) -> str:
    """Render inlined source material for one synthesizer prompt."""
    payloads = _source_payloads(sources, target_dir, kind)
    if not payloads:
        return "_No source changes to consolidate._"

    blocks: list[str] = []
    for payload in payloads:
        blocks.append(
            f"### `{payload['label']}` — {payload['form']}\n\n"
            f"```text\n{payload['body']}\n```"
        )
    return "\n\n".join(blocks)


def _current_content(target_dir: Path, output_name: str) -> str:
    """Return the existing output file verbatim, or a clear empty marker."""
    try:
        content = (target_dir / output_name).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "_This file does not exist yet. Create it with the material below._"
    if not content.strip():
        return "_This file is empty. Fill it with the material below._"
    return content.rstrip()


def _size_note(target_dir: Path, output_name: str) -> str:
    """Return the soft size warning only when the file is genuinely large."""
    try:
        size = len((target_dir / output_name).read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return ""
    if size < LARGE_OUTPUT_CHARS:
        return ""
    return SIZE_NOTE.replace("{{output_name}}", output_name)


def _render(template: str, values: dict[str, Any]) -> str:
    """Replace ``{{token}}`` placeholders, failing loudly on a missing token."""
    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"prompt token {{{{{key}}}}} has no value")
        return str(values[key])

    return _TOKEN_RE.sub(substitute, template).strip() + "\n"


def build_prompt(item: dict[str, Any], kind: str = "memory") -> str:
    """Build the synthesis prompt for one pending node and one output file.

    Args:
        item: One entry from ``walk_memory()["needs_update"]``.
        kind: ``"memory"`` for ``memory.md``, ``"reflections"`` for
            ``reflections.md``.

    Returns:
        The rendered prompt, ready to send to a ``memory-manage`` session.

    Raises:
        ValueError: If the node cannot be classified, its manifest is missing,
            or *kind* is unknown.
        KeyError: If a template references an unknown placeholder.
    """
    if kind not in KIND_OUTPUT:
        raise ValueError(f"unknown synthesis kind: {kind!r}")

    manifest_path = str(item.get("manifest_path") or "")
    if not manifest_path:
        raise ValueError("memory item has no manifest_path")

    manifest_file = Path(manifest_path).expanduser()
    if not manifest_file.is_file():
        raise ValueError(f"memory manifest not found: {manifest_file}")

    manifest = memsources.read_sources(manifest_file)
    layer, scope = _classify(item, manifest)
    target_dir = manifest_file.parent.resolve()
    output_name = KIND_OUTPUT[kind]
    label = _node_label(item, manifest, layer, scope)

    return _render(
        SYNTHESIS_PROMPT,
        {
            "title": _LAYER_TITLES[layer],
            "node_label": label,
            "scope_description": _scope_description(scope, label, layer),
            "target_dir": target_dir.as_posix(),
            "output_name": output_name,
            "current_content": _current_content(target_dir, output_name),
            "changed_sources": _format_sources(
                list(item.get("sources") or []), target_dir, kind
            ),
            "size_note": _size_note(target_dir, output_name),
            "guidance": _LAYER_GUIDANCE[(layer, kind)],
        },
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _item_target_dir(item: dict[str, Any]) -> Path:
    """Return the resolved target directory for a walker item."""
    manifest_path = Path(str(item.get("manifest_path") or ""))
    return manifest_path.parent.resolve()


def _select_batch(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Return pending nodes ready to synthesize, across levels.

    Readiness comes from ``is_up_to_date`` on the walker item: False means one
    of the node's sources has pending synthesis of its own, so the parent must
    wait.  That flag is computed from the memory tree rather than physical
    path containment, so child scopes whose memory dirs are not nested still
    block correctly.  Ready nodes are prioritized deepest-first to unblock
    parents quickly.
    """
    if not items:
        return []

    ready: list[dict[str, Any]] = [
        item for item in items if item.get("is_up_to_date", True)
    ]

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


def _access_overrides(session: Any, target_dir: Path, output_name: str) -> dict[str, Any]:
    """Return a narrow session ``access`` block for one synthesizer.

    Write access covers the node directory (so a size note may create a linked
    spillover file).  Read access is limited to the *one* output file: source
    material is inlined in the prompt, so no source file should be readable.
    """
    resolved = target_dir.resolve()
    write_roots = [resolved]
    read_roots = [resolved / output_name]

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
    _session: Any, layer: str, target_dir: Path, prompt: str, kind: str
) -> dict[str, Any]:
    """Spawn one restricted ``memory-manage`` subtask for one output file."""
    from server.models.enums.session_enums import SessionType

    output_name = KIND_OUTPUT[kind]
    child = _session.spawn_subagent(
        "memory-manage",
        name=f"memory:{layer}:{kind}:{uuid.uuid4().hex[:10]}",
        description=f"{layer} {kind}: {_display_target(target_dir)}",
        session_type=SessionType.SUBTASK_DELEGATE,
        group_key=f"memory:{layer}",
        allow_internal=True,
        access=_access_overrides(_session, target_dir, output_name),
        disallowedToolNames=SYNTHESIZER_DISALLOWED_TOOLS,
        disallowedTaskNames=SYNTHESIZER_DISALLOWED_TASKS,
        tool_call_allowlist=SYNTHESIZER_TOOL_ALLOWLIST,
        max_turns=SYNTHESIZER_MAX_TURNS,
    )
    if child is None:
        return {"status": "error", "error": "agent 'memory-manage' not found"}

    call = child.add_user_message(prompt)
    return {
        "status": "dispatched",
        "kind": kind,
        "session_pk": child.model.pk,
        "call": call,
    }


def memory_merge_item(_session: Any, item: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Synthesize one pending memory node with two parallel subtasks.

    Both synthesizer task calls are handed to ``memory_finalize``.  The
    framework waits for *all* argument references to end, then passes both
    results to the finalize task, which advances the manifest once.
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

    finalize_task = _session.get_task("memory_finalize")
    if finalize_task is None:
        return False, {
            **outcome,
            "status": "error",
            "error": "task 'memory_finalize' is not available to this session",
        }

    started_at = time.time()
    spawned: dict[str, dict[str, Any]] = {}
    try:
        for kind in ("memory", "reflections"):
            spawn = _spawn_synthesizer(
                _session, layer, target_dir, build_prompt(item, kind), kind
            )
            spawned[kind] = spawn
            if spawn["status"] != "dispatched":
                raise RuntimeError(spawn["error"])
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _clear_inflight(target_dir)
        return False, {**outcome, "status": "error", "error": str(exc)}

    first = next(iter(spawned.values()))
    _write_inflight(target_dir, first["session_pk"], layer, started_at)
    try:
        finalize_call = finalize_task.delay(
            spawned["memory"]["call"],
            spawned["reflections"]["call"],
            target_dir=target_dir.resolve().as_posix(),
            started_at=started_at,
        )
    except Exception:
        _clear_inflight(target_dir)
        raise

    outcome.update({
        "status": "dispatched",
        "sessions": {
            kind: spawn["session_pk"] for kind, spawn in spawned.items()
        },
        "finalize_call_pk": getattr(finalize_call, "pk", None),
        "finalize": finalize_call,
    })
    return True, outcome


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

    # Ready nodes are independent (no pending descendant). Keep map concurrency
    # sequential: each item already runs its two synthesizers in parallel.
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
    dispatches them as ``memory_merge_item`` map tasks. Each item spawns two
    synthesizer subtasks (memory + reflections) and chains one finalize call
    that waits for both.

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
