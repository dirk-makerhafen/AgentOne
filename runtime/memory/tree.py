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


def _compute_memory_type(kind: str, scope: str, path: Path) -> str:
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

    def link(parent: Optional[MemoryNode], child: MemoryNode) -> None:
        if parent is None or parent is child:
            return
        bucket = children.setdefault(id(parent), [])
        if all(id(existing) != id(child) for existing in bucket):
            bucket.append(child)

    for node in project_nodes.values():
        link(global_node, node)

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
        link(parent, node)

    return ScopeIndex(global_node, project_nodes, workspace_nodes, children)


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
        child_pk = int(child.key) if str(child.key).isdigit() else None
        child_type = _compute_memory_type(child.kind, node.scope, child.path)
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
        "type": _compute_memory_type(node.kind, node.scope, node.path),
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


def walk_memory(write: bool = True) -> dict[str, Any]:
    """Walk every existing memory root and update ``.memory_sources.md``.

    With ``write=False`` only reports what would be written.  Returns a
    summary with node/manifest counts, pending sources and warnings.
    """
    tree = discover_tree()
    if write:
        _prepare_write_repos(tree)
    manifests_written = 0
    pending = 0
    missing = 0

    for node in tree.nodes:
        payload = _build_manifest(node, tree)
        for source in payload["sources"]:
            last = source.get("last_processed_hash")
            current = source.get("current_hash")
            if current is None:
                missing += 1
            elif last != current:
                pending += 1

        manifest_path = node.path / memsources.SOURCES_FILENAME
        if not write:
            continue
        try:
            if memsources.write_sources(manifest_path, payload):
                manifests_written += 1
        except OSError as exc:
            tree.warnings.append(f"write failed for {manifest_path}: {exc}")

    return {
        "nodes": len(tree.nodes),
        "manifests_written": manifests_written,
        "pending": pending,
        "missing": missing,
        "warnings": tree.warnings,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
