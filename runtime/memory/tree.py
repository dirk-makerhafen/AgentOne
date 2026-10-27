"""Top-down memory tree discovery and ``.memory_sources.md`` generation.

Each synthesised layer gets one gitignored manifest with its source paths,
the git commit seen at the last synthesis and the current commit::

    scope root -> agents/ + each direct child scope's memory directory
    agent      -> tasks/
    task       -> sessions/

Sessions have no manifest; their reports are covered by the task's
``sessions/`` commit.  This module only writes that manifest; it never runs
synthesis.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from django.db.models import Prefetch

from runtime.memory import git as memgit
from runtime.memory import paths as mempaths
from runtime.memory import sources as memsources

_SCOPE_KINDS = {"global", "project", "workspace"}
_SOURCE_DIR = {
    "global": "agents",
    "project": "agents",
    "workspace": "agents",
    "agent": "tasks",
    "task": "sessions",
}
_AGENT_QUERY_CHUNK = 500
_REPORT_BATCH_SIZE = 250


def _compute_memory_type(kind: str, scope: str) -> str:
    """Return the memory type string for a node.

    The type encodes the scope kind plus the entity layer:
      global, project, workspace              – scope roots
      <scope>-agent                           – agent layer
      <scope>-agent-task                      – task layer
    """
    if kind in _SCOPE_KINDS:
        return kind
    if kind == "agent":
        return f"{scope}-agent"
    if kind == "task":
        return f"{scope}-agent-task"
    return kind


def _source_type(node_scope: str, source_dir: str) -> str:
    """Return the type for a directory-level source entry.

    Maps the child layer directory name to a pluralised type string:
      agents  → <scope>-agents
      tasks   → <scope>-agent-tasks
      sessions→ <scope>-agent-task-sessions
    """
    prefix = node_scope
    if source_dir == "tasks":
        prefix += "-agent"
    elif source_dir == "sessions":
        prefix += "-agent-task"
    return f"{prefix}-{source_dir}"


@dataclass
class MemoryNode:
    """A memory layer that owns a ``.memory_sources.md`` manifest."""

    kind: str
    key: str
    name: str
    path: Path
    scope: str = ""  # parent scope kind (global/project/workspace); defaults to kind for roots


@dataclass
class MemoryTree:
    """Discovery result: flat manifest targets plus non-fatal warnings."""

    nodes: list[MemoryNode] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scope_children: dict[int, list[MemoryNode]] = field(default_factory=dict)
    node_depth: dict[int, int] = field(default_factory=dict)


def _compute_depths(tree: MemoryTree) -> dict[int, int]:
    """Compute depth for each node (distance from global root)."""
    if not tree.nodes:
        return {}
    # Find global root (scope is empty or same as kind)
    global_root = next(
        (n for n in tree.nodes if not n.scope or n.scope == n.kind), None
    )
    if global_root is None:
        return {}

    depths: dict[int, int] = {id(global_root): 0}
    queue = [global_root]
    visited = {id(global_root)}

    while queue:
        parent = queue.pop(0)
        parent_depth = depths[id(parent)]
        for child in tree.scope_children.get(id(parent), []):
            if id(child) not in visited:
                depths[id(child)] = parent_depth + 1
                visited.add(id(child))
                queue.append(child)

    # Assign depth 0 to any unvisited roots (shouldn't happen, but be safe)
    for node in tree.nodes:
        if id(node) not in depths:
            depths[id(node)] = 0

    tree.node_depth = depths
    return depths


@dataclass
class ScopeIndex:
    """Scope nodes looked up by the DB IDs that point at them."""

    global_node: Optional[MemoryNode] = None
    projects: dict[int, MemoryNode] = field(default_factory=dict)
    workspaces: dict[int, MemoryNode] = field(default_factory=dict)
    children: dict[int, list[MemoryNode]] = field(default_factory=dict)


def _norm_path(path: Any) -> str:
    try:
        value = os.path.realpath(os.path.expanduser(str(path)))
    except (OSError, ValueError):
        value = os.path.normpath(os.path.expanduser(str(path)))
    return value.rstrip(os.sep) or os.sep


def _is_within(child: Any, parent: Any) -> bool:
    child_norm = _norm_path(child)
    parent_norm = _norm_path(parent)
    return bool(parent_norm) and child_norm != parent_norm and child_norm.startswith(parent_norm + os.sep)


def _source_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.resolve().as_posix()


def _strip_prefix(name: str, prefix: str) -> str:
    return name[len(prefix):] if name.startswith(prefix) else name


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_tree() -> MemoryTree:
    """Discover existing memory roots and the layers that own manifests."""
    tree = MemoryTree()
    scopes = _discover_scopes(tree)
    tree.scope_children = scopes.children
    _discover_entities(tree, scopes)
    return tree


def _discover_scopes(tree: MemoryTree) -> ScopeIndex:
    from server.models.project import Project
    from server.models.workspace import WorkspaceModel

    seen: dict[str, MemoryNode] = {}
    project_nodes: dict[int, MemoryNode] = {}
    workspace_nodes: dict[int, MemoryNode] = {}
    workspace_meta: list[tuple[MemoryNode, Optional[Path], int]] = []

    global_root = mempaths.memory_root()
    global_node: Optional[MemoryNode] = None
    if global_root.is_dir():
        global_node = MemoryNode("global", "global", "global", global_root, "global")
        tree.nodes.append(global_node)
        seen[_norm_path(global_root)] = global_node

    for project in Project.objects.select_related("main_workspace").order_by("pk"):
        root = mempaths.memory_root(project=project)
        if not root.is_dir():
            continue
        norm = _norm_path(root)
        if norm in seen:
            project_nodes[project.pk] = seen[norm]
            tree.warnings.append(
                f"project {project.pk} memory root duplicates "
                f"{seen[norm].kind} {seen[norm].key}: {root}"
            )
            continue
        node = MemoryNode(
            "project",
            str(project.pk),
            project.name or f"project {project.pk}",
            root,
            "project",
        )
        tree.nodes.append(node)
        seen[norm] = node
        project_nodes[project.pk] = node

    for workspace in WorkspaceModel.objects.select_related("parent_project").order_by("pk"):
        root = mempaths.memory_root(workspace=workspace)
        if not root.is_dir():
            continue
        norm = _norm_path(root)
        if norm in seen:
            workspace_nodes[workspace.pk] = seen[norm]
            tree.warnings.append(
                f"workspace {workspace.pk} memory root duplicates "
                f"{seen[norm].kind} {seen[norm].key}: {root}"
            )
            continue
        node = MemoryNode(
            "workspace",
            str(workspace.pk),
            workspace.name or workspace.path or f"workspace {workspace.pk}",
            root,
            "workspace",
        )
        tree.nodes.append(node)
        seen[norm] = node
        workspace_nodes[workspace.pk] = node
        workspace_meta.append(
            (node, Path(workspace.path) if workspace.path else None, workspace.parent_project_id)
        )

    children: dict[int, list[MemoryNode]] = {}

    for node in project_nodes.values():
        _add_child(children, global_node, node)

    for node, ws_path, parent_proj_id in workspace_meta:
        enclosing = [
            (other, other_path)
            for other, other_path, _ in workspace_meta
            if other is not node and ws_path and other_path and _is_within(ws_path, other_path)
        ]
        if enclosing:
            parent = max(enclosing, key=lambda item: len(_norm_path(item[1])))[0]
        else:
            parent = project_nodes.get(parent_proj_id) or global_node
        _add_child(children, parent, node)

    return ScopeIndex(global_node, project_nodes, workspace_nodes, children)


def _add_child(children: dict[int, list[MemoryNode]], parent: Optional[MemoryNode], child: MemoryNode) -> None:
    """Add *child* to *parent* in the ``children`` index."""
    if parent is None or parent is child:
        return
    bucket = children.setdefault(id(parent), [])
    if all(id(existing) != id(child) for existing in bucket):
        bucket.append(child)


def _discover_entities(tree: MemoryTree, scopes: ScopeIndex) -> None:
    """Add agent/task nodes for existing memory, validated by the DB.

    Listing existing ``agents/*`` directories narrows the DB query to agents
    that actually have memory.  The DB remains authoritative: a directory is
    only materialised when a ``SessionVersionModel`` row maps it to a scope,
    and ``SessionModel.group_key`` names the task layer.
    """
    scope_agent_dirs: dict[int, dict[int, Path]] = {}
    candidate_agents: set[int] = set()
    for node in tree.nodes:
        if node.kind not in _SCOPE_KINDS or id(node) in scope_agent_dirs:
            continue
        agent_dirs = _list_agent_dirs(node.path)
        scope_agent_dirs[id(node)] = agent_dirs
        candidate_agents.update(agent_dirs)

    if not candidate_agents:
        return

    agents: dict[tuple[int, int], MemoryNode] = {}
    tasks: dict[tuple[int, str], MemoryNode] = {}
    task_cache: dict[tuple[Path, str], Optional[Path]] = {}

    for agent_id, workspace_id, project_id, group_key in _session_groups(candidate_agents):
        scope = _scope_for_row(scopes, workspace_id, project_id)
        if scope is None:
            continue
        agent_dir = scope_agent_dirs.get(id(scope), {}).get(agent_id)
        if agent_dir is None:
            continue

        agent = agents.get((id(scope), agent_id))
        if agent is None:
            agent = MemoryNode("agent", str(agent_id), agent_dir.name, agent_dir, scope.kind)
            tree.nodes.append(agent)
            agents[(id(scope), agent_id)] = agent
        _add_child(scopes.children, scope, agent)

        group = (group_key or "").strip() or "default"
        cache_key = (agent_dir, group)
        if cache_key not in task_cache:
            candidate_dir = mempaths.task_memory_dir(agent_dir, group)
            task_cache[cache_key] = candidate_dir if candidate_dir.is_dir() else None
        task_dir = task_cache[cache_key]
        if task_dir is None:
            continue

        task_key = _strip_prefix(task_dir.name, "task_")
        if (id(agent), task_key) not in tasks:
            task = MemoryNode("task", task_key, task_dir.name, task_dir, agent.scope)
            tree.nodes.append(task)
            tasks[(id(agent), task_key)] = task
        _add_child(scopes.children, agent, task)


def _list_agent_dirs(scope_root: Path) -> dict[int, Path]:
    """Return ``agent_pk -> directory`` for an existing memory scope."""
    agents_dir = scope_root / "agents"
    try:
        entries = list(agents_dir.iterdir())
    except OSError:
        return {}
    found: dict[int, Path] = {}
    for entry in entries:
        if entry.name.startswith(".") or not entry.is_dir():
            continue
        raw = _strip_prefix(entry.name, "agent_")
        if not raw.isdigit():
            continue
        found[int(raw)] = entry
    return found


def _session_groups(agent_ids: set[int]):
    """Yield distinct ``(agent_id, workspace_id, project_id, group_key)`` rows.

    Only agents with an existing memory directory are queried, and the query
    is chunked to stay within SQLite's parameter limit.
    """
    from server.models.sessions.session_version import SessionVersionModel

    ids = sorted(agent_ids)
    for start in range(0, len(ids), _AGENT_QUERY_CHUNK):
        chunk = ids[start:start + _AGENT_QUERY_CHUNK]
        yield from (
            SessionVersionModel.objects
            .filter(agent_id__in=chunk)
            .values_list(
                "agent_id",
                "workspace_id",
                "session__parent_project_id",
                "session__group_key",
            )
            .distinct()
        )


def _scope_for_row(
    scopes: ScopeIndex, workspace_id: Optional[int], project_id: Optional[int]
) -> Optional[MemoryNode]:
    if workspace_id is not None:
        return scopes.workspaces.get(workspace_id)
    if project_id is not None:
        return scopes.projects.get(project_id)
    return scopes.global_node


# ---------------------------------------------------------------------------
# Manifest construction
# ---------------------------------------------------------------------------


def _has_content(path: Path) -> bool:
    if path.is_file():
        return not memsources.is_metadata_path(path)
    if not path.is_dir():
        return False
    return any(
        candidate.is_file() and not memsources.is_metadata_path(candidate)
        for candidate in path.rglob("*")
    )

def _source_entry(
    label: str,
    source: Path,
    previous: dict[str, Any],
    previous_by_identity: Optional[dict[int, Any]] = None,
    pk: Optional[int] = None,
    source_type: Optional[str] = None,
) -> dict[str, Any]:
    has_content = _has_content(source)
    current = memgit.path_commit(source) if has_content else None
    last = None
    if pk is not None and previous_by_identity:
        last = previous_by_identity.get(pk)
    if last is None:
        last = previous.get(label)
    if last is not None and not memgit.is_git_hash(last):
        last = None

    hours = None
    changed = None
    if last and current:
        stats = memgit.diff_stats(source, last, current)
        if stats is None:
            last = None
        else:
            hours, changed = stats

    entry: dict[str, Any] = {"path": label}
    if pk is not None:
        entry["pk"] = pk
    if source_type is not None:
        entry["type"] = source_type
    entry.update({
        "last_processed_hash": last,
        "current_hash": current,
        "hours_since_processed": hours,
        "changed_chars": changed,
    })
    return entry


def _build_manifest(node: MemoryNode, tree: MemoryTree) -> dict[str, Any]:
    manifest_path = node.path / memsources.SOURCES_FILENAME
    previous_manifest = memsources.read_sources(manifest_path)
    previous = memsources.previous_hashes(previous_manifest)
    previous_by_identity = memsources.previous_by_identity(previous_manifest)

    source_dir = _SOURCE_DIR[node.kind]
    dir_type = _source_type(node.scope, source_dir)
    sources = [
        _source_entry(
            f"{source_dir}/",
            node.path / source_dir,
            previous,
            previous_by_identity=previous_by_identity,
            source_type=dir_type,
        )
    ]
    for child in tree.scope_children.get(id(node), []):
        # Only scope-level children (projects, workspaces) are listed as
        # individual sources; agent/task/session directories are covered
        # by the generic ``agents/``, ``tasks/``, ``sessions/`` entries.
        if child.kind not in _SCOPE_KINDS:
            continue
        child_pk = int(child.key) if str(child.key).isdigit() else None
        child_type = _compute_memory_type(child.kind, node.scope)
        sources.append(
            _source_entry(
                _source_path(child.path, node.path),
                child.path,
                previous,
                previous_by_identity=previous_by_identity,
                pk=child_pk,
                source_type=child_type,
            )
        )

    return {
        "kind": node.kind,
        "type": _compute_memory_type(node.kind, node.scope),
        "key": node.key,
        "name": node.name,
        "sources": sources,
    }


def _prepare_write_repos(tree: MemoryTree) -> None:
    for node in tree.nodes:
        if node.kind not in _SCOPE_KINDS:
            continue
        try:
            memgit.ensure_repo(node.path)
            memgit.commit_all(node.path, message="memory: walk")
        except OSError as exc:
            tree.warnings.append(f"git sync failed for {node.path}: {exc}")


def mark_processed(target_dir: Path) -> bool:
    """Snapshot current source commits as last-processed for *target_dir*.

    Called after a successful synthesis.  The walker itself never advances
    ``last_processed_hash``.
    """
    tree = discover_tree()
    target = Path(target_dir).resolve()
    node = next((n for n in tree.nodes if n.path.resolve() == target), None)
    if node is None:
        return False

    children = tree.scope_children.get(id(node), [])
    if node.kind in _SCOPE_KINDS:
        memgit.ensure_repo(node.path)
    for child in children:
        memgit.ensure_repo(child.path)

    repo = memgit.repo_for(node.path)
    if repo is not None:
        memgit.commit_all(repo, message="memory: synthesized")
    for child in children:
        memgit.commit_all(child.path, message="memory: synthesized")

    payload = _build_manifest(node, tree)
    for source in payload["sources"]:
        current = source.get("current_hash")
        source["last_processed_hash"] = current
        source["hours_since_processed"] = 0.0 if current else None
        source["changed_chars"] = 0 if current else None
    memsources.write_sources(node.path / memsources.SOURCES_FILENAME, payload)
    return True


def _report_dir(session: Any, version: Any) -> Optional[Path]:
    """Return the task memory directory that owns *session*'s reports.

    The scope root is resolved from the session *version* that produced the
    message: a workspace-bound session belongs to the workspace memory root,
    not to its parent project's root.  Returns ``None`` when the scope cannot
    be resolved.
    """
    try:
        resolved_root = mempaths.memory_root(
            session_or_pk=session,
            workspace=version.workspace,
            project=session.parent_project,
        )
        agent_dir = mempaths.agent_memory_dir(resolved_root, version.agent_id)
        return mempaths.task_memory_dir(agent_dir, session.group_key)
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _refresh_reports() -> dict[str, int]:
    """Save every REFLECTION/COMPACTION message to task memory directories.

    Iterates all report messages in the database, resolves the task memory
    directory for the session version that produced each message, and writes
    the message content to its timestamped report file if that file does not
    exist yet.  Report filenames are derived from the message timestamp and
    pk, so re-running is idempotent.

    Missing ``agents/<pk>/tasks/<task>/sessions/<pk>/`` directories are
    created as needed — a session does not have to have been synthesized
    before its reports can be persisted.

    Returns:
        A dict with keys ``"reflections_written"`` and
        ``"compactions_written"`` counting how many report files were
        created during this call.
    """
    from server.models.enums.message_enums import MessageType
    from server.models.message import Message, MessagePart

    counts = {"reflections_written": 0, "compactions_written": 0}

    queryset = (
        Message.objects
        .filter(
            message_type__in=[MessageType.REFLECTION, MessageType.COMPACTION]
        )
        .select_related("session", "session_version__workspace")
        .prefetch_related(
            Prefetch(
                "parts",
                queryset=MessagePart.objects
                .select_related("content")
                .order_by("pk"),
                to_attr="report_parts",
            )
        )
        .order_by("pk")
    )

    # Report directory per (session, version, task group); sessions can change
    # agent/workspace over their lifetime, so each version is looked up once.
    report_dirs: dict[tuple[int, int, str], Optional[Path]] = {}

    # Walk in pk batches so a large history does not load everything at once.
    last_pk = 0
    while True:
        batch = list(queryset.filter(pk__gt=last_pk)[:_REPORT_BATCH_SIZE])
        if not batch:
            break
        last_pk = batch[-1].pk

        for msg in batch:
            session = msg.session
            version = msg.session_version or getattr(
                session, "latest_session_version", None
            )
            if session is None or version is None or version.agent_id is None:
                continue

            group_key = (session.group_key or "").strip() or "default"
            cache_key = (session.pk, version.pk, group_key)
            if cache_key not in report_dirs:
                report_dirs[cache_key] = _report_dir(session, version)
            task_dir = report_dirs[cache_key]
            if task_dir is None:
                continue

            report_path = (
                mempaths.session_memory_dir(task_dir, session.pk)
                / mempaths.report_filename(msg)
            )
            if report_path.exists():
                continue

            try:
                content = extract_report_text(msg)
                if not content:
                    continue
                mempaths.write_text(report_path, content)
            except OSError:
                continue

            if msg.message_type == MessageType.REFLECTION:
                counts["reflections_written"] += 1
            else:
                counts["compactions_written"] += 1

    return counts


def extract_report_text(message: Any) -> str:
    """Extract the plain-text body of a report message.

    Reflection reports carry their text in ``MESSAGE`` parts; compaction
    markers carry it in ``COMPACTION`` parts.  Both are included, while
    ``REASONING``/``TOOLCALL`` parts are skipped.  For compaction markers the
    trailing session-bootstrap parts (re-pinned agent templates and workspace
    guidance) are dropped: they are re-sent to the LLM after every compaction
    and are not part of the summary.
    """
    from server.models.enums.message_enums import MessageContentType

    parts = getattr(message, "report_parts", None)
    if parts is None:
        manager = getattr(message, "parts", None)
        if manager is None:
            return ""
        try:
            parts = list(manager.order_by("pk"))
        except Exception:  # pylint: disable=broad-exception-caught
            return ""

    sentinel = ""
    try:
        from runtime.session_bootstrap import COMPACTION_BOOTSTRAP_SENTINEL

        sentinel = COMPACTION_BOOTSTRAP_SENTINEL
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    texts: list[str] = []
    try:
        for part in parts:
            part_type = str(getattr(part, "type", "") or "").upper()
            if part_type not in ("MESSAGE", "COMPACTION"):
                continue
            if part.content_type != MessageContentType.TEXT:
                continue
            content = part.content.get() if part.content else None
            if not content:
                continue
            text = str(content)
            if sentinel and sentinel in text:
                break
            texts.append(text)
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    return "\n".join(texts) if texts else ""


def walk_memory(write: bool = True, refresh: bool = False) -> dict[str, Any]:
    """Walk every existing memory root and update ``.memory_sources.md``.

    Scans all memory roots (global, per-workspace, per-project, per-agent)
    for ``.memory_sources.md`` manifests.  Rebuilds any that are missing or
    out of date, recording git commit hashes so future runs can detect
    changes.

    Args:
        write: When ``True`` (default), actually writes/updates manifest
            files on disk.  When ``False``, only computes what *would* be
            written — useful for dry-run inspection.
        refresh: When ``True``, queries the database for every REFLECTION
            and COMPACTION message and saves any that are not already
            present as report files in the corresponding task memory
            directory (scoped to the workspace/project the message's
            session version belongs to).  This backfills reports that were
            never persisted to the filesystem.

    Returns:
        A summary dict with:

        - ``nodes`` – number of memory nodes scanned.
        - ``manifests_written`` – count of ``.memory_sources.md`` files
          written or updated.
        - ``pending`` – sources whose hash changed since last processed.
        - ``missing`` – sources without a manifest yet.
        - ``warnings`` – list of warning strings.
        - ``generated_at`` – ISO-8601 timestamp.
        - ``needs_update`` – list of manifests that need rewriting.
          Each entry has:

          - ``manifest_path`` – absolute path to the
            ``.memory_sources.md`` file.
          - ``node_kind`` – scope / agent / task.
          - ``node_key`` – primary-key or key string.
          - ``depth`` – distance from global root.
          - ``sources`` – list of changed sources with their
            ``path``, ``type``, ``pk``, ``changed_chars``,
            ``hours_since_processed``, ``last_processed_hash``,
            and ``current_hash``.
        - ``reflections_written`` – only present when ``refresh=True``;
          count of new reflection report files saved.
        - ``compactions_written`` – only present when ``refresh=True``;
          count of new compaction report files saved.
    """
    # Backfill report files first so their git commits and directories are
    # visible to discovery/commit/manifest generation in this same run.
    refresh_counts: dict[str, int] = {}
    if refresh:
        refresh_counts = _refresh_reports()

    tree = discover_tree()
    _compute_depths(tree)
    if write:
        _prepare_write_repos(tree)

    manifests_written = 0
    pending = 0
    missing = 0
    # Group changed sources by the manifest node that owns them.
    # Each entry: {"manifest_path": str, "node_kind": str, "node_key": str,
    #              "depth": int, "sources": [{...}, ...]}
    needs_update: dict[int, dict[str, Any]] = {}

    for node in tree.nodes:
        payload = _build_manifest(node, tree)
        node_depth = tree.node_depth.get(id(node), 0)
        node_needs_update: list[dict[str, Any]] = []

        for source in payload["sources"]:
            last = source.get("last_processed_hash")
            current = source.get("current_hash")
            if current is None:
                missing += 1
            elif last != current:
                pending += 1
                node_needs_update.append({
                    "path": source["path"],
                    "type": source.get("type"),
                    "pk": source.get("pk"),
                    "changed_chars": source.get("changed_chars"),
                    "hours_since_processed": source.get("hours_since_processed"),
                    "last_processed_hash": last,
                    "current_hash": current,
                })

        if node_needs_update:
            manifest_path = str(node.path / memsources.SOURCES_FILENAME)
            needs_update[id(node)] = {
                "manifest_path": manifest_path,
                "node_kind": node.kind,
                "node_key": node.key,
                "type": _compute_memory_type(node.kind, node.scope),
                "depth": node_depth,
                "sources": node_needs_update,
            }

        # Write manifest
        manifest_path = node.path / memsources.SOURCES_FILENAME
        if not write:
            continue
        try:
            if memsources.write_sources(manifest_path, payload):
                manifests_written += 1
        except OSError as exc:
            tree.warnings.append(f"write failed for {manifest_path}: {exc}")

    # Sort: depth-first (descending), then by total changed_chars descending
    needs_update_list = list(needs_update.values())
    needs_update_list.sort(
        key=lambda s: (-s["depth"], -(sum(src.get("changed_chars") or 0 for src in s["sources"])))
    )


    return {
        "nodes": len(tree.nodes),
        "manifests_written": manifests_written,
        "pending": pending,
        "missing": missing,
        "warnings": tree.warnings,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "needs_update": needs_update_list,
        **refresh_counts,
    }
