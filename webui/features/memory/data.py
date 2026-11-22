"""Read-only data layer for the Memory UI.

The memory system is a tree on disk, not a database table::

    <scope>/memory/
        memory.md  reflection.md  improvements.md  .memory_sources.md
        agents/<agent_pk>/
            memory.md  reflection.md  improvements.md  .memory_sources.md
            tasks/task_<group_key>/
                memory.md  reflection.md  improvements.md  .memory_sources.md
                sessions/

This module turns that tree into plain objects the views can render.  It is
deliberately free of  imports so the same helpers can be unit-tested
without a live UI instance.

Two rules matter:

* **Read-only.**  Nothing here writes a memory file or runs the memory walker.
  ``.memory_sources.md`` is a snapshot from the last walk; the UI labels it
  "as of" rather than pretending it is live.
* **The schema module owns parsing.**  Playbooks and proposals are parsed by
  the same ``playbook`` module the synthesizer writes against, so the UI can
  never drift from what injection actually consumes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

MEMORY_FILENAME = "memory.md"
REFLECTIONS_FILENAME = "reflections.md"
SOURCES_FILENAME = ".memory_sources.md"

# Legacy artifacts kept readable during transition.
LEGACY_REFLECTION_FILENAME = "reflection.md"
LEGACY_IMPROVEMENTS_FILENAME = "improvements.md"

#: Files that make a directory a memory node.
NODE_FILES = (
    MEMORY_FILENAME,
    REFLECTIONS_FILENAME,
    SOURCES_FILENAME,
    LEGACY_REFLECTION_FILENAME,
    LEGACY_IMPROVEMENTS_FILENAME,
)

#: Defensive cap: the tree is small, but a pathological scope must not stall
#: the UI thread while a tab renders.
MAX_NODES = 400

#: Excerpt budget for the sidebar/overview.  Full text is read on demand by
#: the node detail view.
EXCERPT_CHARS = 220

#: Most specific first.  Used to decide which layer owns a duplicate proposal.
SCOPE_SPECIFICITY = {"workspace": 0, "project": 1, "global": 2}

#: Most specific first *inside* a scope.  Mirrors the injection resolution
#: order documented in ``docs/self-improvement.md`` (task → agent → scope).
DIRECTIVE_LAYER = {"task": 0, "agent": 1, "scope": 2}

#: Routings the session bootstrap never injects (see ``memory_playbook.py``).
NON_INJECTABLE_ROUTING = {"harness", "memory"}

#: Proposal ordering in the improvements list.
PROPOSAL_RANK = {
    "specified": 0,
    "candidate": 1,
    "implemented": 2,
    "active": 3,
    "retired": 4,
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _schema() -> Any:
    from runtime.memory_playbook import schema_module

    return schema_module()


def _read_text(path: Path, limit: int | None = None) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read() if limit is None else handle.read(limit)
    except OSError:
        return ""


def _strip_prefix(name: str, prefix: str) -> str:
    return name[len(prefix):] if name.startswith(prefix) else name


def _int_suffix(name: str, prefix: str) -> int | None:
    raw = _strip_prefix(name, prefix)
    return int(raw) if raw.isdigit() else None


def _iter_dirs(path: Path) -> list[Path]:
    try:
        entries = list(path.iterdir())
    except OSError:
        return []
    return sorted(
        (entry for entry in entries if entry.is_dir() and not entry.name.startswith(".")),
        key=lambda entry: entry.name,
    )


def _has_content(path: Path) -> bool:
    return any((path / name).is_file() for name in NODE_FILES)


def _excerpt(text: str) -> str:
    """Return a short, readable gist (first prose lines, not headings)."""
    lines = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line in {"---", "```"}:
            continue
        lines.append(line)
        if sum(len(item) for item in lines) >= EXCERPT_CHARS:
            break
    if not lines:
        return ""
    text = " ".join(" ".join(lines).split())
    if len(text) > EXCERPT_CHARS:
        text = text[: EXCERPT_CHARS - 1].rstrip() + "…"
    return text


def _format_timestamp(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return parsed.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Scope references
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryScopeRef:
    """One scope whose ``memory/`` directory can be inspected."""

    kind: str  # global | project | workspace
    key: str
    name: str
    root: Path
    project_id: int | None = None


def _add_ref(
    refs: list[MemoryScopeRef],
    seen: set[str],
    kind: str,
    key: str,
    name: str,
    root: Path,
    project_id: int | None = None,
) -> None:
    root = Path(root).expanduser()
    marker = root.as_posix()
    if marker in seen:
        return
    seen.add(marker)
    refs.append(MemoryScopeRef(kind, str(key), name or kind, root, project_id))


def scope_refs(project_id: int | None = None) -> list[MemoryScopeRef]:
    """Return the memory scopes to show.

    Global always comes first.  With no project selected the inventory is the
    union of every project and workspace; with a project selected it is global
    plus that project and its workspaces.
    """
    from runtime.paths import ScopeRef, user_memory_dir

    refs: list[MemoryScopeRef] = []
    seen: set[str] = set()
    _add_ref(refs, seen, "global", "global", "Global", user_memory_dir())

    try:
        from server.models.project import Project

        projects = (
            Project.objects.filter(pk=project_id).order_by("name")
            if project_id is not None
            else Project.objects.all().order_by("name")
        )
        for project in projects:
            ref = ScopeRef.for_project(project)
            _add_ref(
                refs,
                seen,
                "project",
                ref.key,
                project.name or "Project",
                ref.manifest_dir / "memory",
                project.pk,
            )
    except Exception:  # pylint: disable=broad-exception-caught
        # The UI is still useful with the global scope when the DB is cold.
        pass

    try:
        from server.models.workspace import WorkspaceModel

        workspaces = (
            WorkspaceModel.objects.filter(parent_project_id=project_id).order_by("name")
            if project_id is not None
            else WorkspaceModel.objects.all().order_by("name")
        )
        for workspace in workspaces:
            ref = ScopeRef.for_workspace(workspace)
            _add_ref(
                refs,
                seen,
                "workspace",
                ref.key,
                workspace.name or "Workspace",
                ref.manifest_dir / "memory",
                workspace.parent_project_id,
            )
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    return refs


# ---------------------------------------------------------------------------
# Parsed file models
# ---------------------------------------------------------------------------


@dataclass
class MemorySource:
    """One row of a ``.memory_sources.md`` manifest."""

    path: str = ""
    type: str = ""
    last_processed_hash: str = ""
    current_hash: str = ""
    changed_chars: int = 0
    depth: int = 0
    is_up_to_date: bool = True

    @property
    def status(self) -> str:
        if not self.current_hash:
            return "missing"
        if self.last_processed_hash != self.current_hash:
            return "pending"
        return "current"

    @property
    def status_label(self) -> str:
        return {"missing": "Missing", "pending": "Changed", "current": "Current"}[
            self.status
        ]


@dataclass
class MemoryNode:
    """One memory layer on disk (scope root, agent, or task)."""

    id: str
    kind: str  # scope | agent | task
    scope: "MemoryScope"
    path: Path
    agent_pk: int | None = None
    agent_name: str = ""
    group_key: str = ""
    sources: list[MemorySource] = field(default_factory=list)
    sources_generated_at: str = ""
    directives: list[dict[str, Any]] = field(default_factory=list)
    playbook_present: bool = False
    playbook_legacy: bool = False
    playbook_metadata: dict[str, Any] = field(default_factory=dict)
    proposals: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    memory_excerpt: str = ""
    memory_chars: int = 0
    _memory_text: str | None = field(default=None, repr=False)

    # -- identity -----------------------------------------------------
    @property
    def label(self) -> str:
        if self.kind == "scope":
            return "Scope root"
        if self.kind == "agent":
            return self.agent_name or f"Agent #{self.agent_pk}"
        return f"Task · {self.group_key or 'default'}"

    @property
    def name(self) -> str:
        """Titlebar name (``AppTitlebar`` reads ``subject.name``)."""
        return self.label

    @property
    def kind_label(self) -> str:
        return {"scope": "Scope", "agent": "Agent", "task": "Task"}.get(
            self.kind, self.kind.title()
        )

    @property
    def relative_path(self) -> str:
        try:
            return self.path.relative_to(self.scope.root).as_posix() or "."
        except ValueError:
            return self.path.name

    # -- file paths ---------------------------------------------------
    @property
    def memory_path(self) -> Path:
        return self.path / MEMORY_FILENAME

    @property
    def reflections_path(self) -> Path:
        return self.path / REFLECTIONS_FILENAME

    @property
    def legacy_reflection_path(self) -> Path:
        return self.path / LEGACY_REFLECTION_FILENAME

    @property
    def legacy_improvements_path(self) -> Path:
        return self.path / LEGACY_IMPROVEMENTS_FILENAME

    @property
    def sources_path(self) -> Path:
        return self.path / SOURCES_FILENAME

    def read_memory(self) -> str:
        if self._memory_text is None:
            self._memory_text = _read_text(self.memory_path)
        return self._memory_text

    def read_reflections(self) -> str:
        return _read_text(self.reflections_path)

    def read_legacy_reflection(self) -> str:
        return _read_text(self.legacy_reflection_path)

    def read_legacy_improvements(self) -> str:
        return _read_text(self.legacy_improvements_path)

    # Backward-compatible aliases used by older templates/code.
    def read_reflection(self) -> str:
        if self.has_reflections:
            return self.read_reflections()
        return self.read_legacy_reflection()

    def read_sources_raw(self) -> str:
        return _read_text(self.sources_path)

    # -- presence / health -------------------------------------------
    @property
    def has_memory(self) -> bool:
        return self.memory_path.is_file()

    @property
    def has_reflections(self) -> bool:
        return self.reflections_path.is_file()

    @property
    def has_legacy_reflection(self) -> bool:
        return self.legacy_reflection_path.is_file()

    @property
    def has_legacy_improvements(self) -> bool:
        return self.legacy_improvements_path.is_file()

    @property
    def has_sources(self) -> bool:
        return self.sources_path.is_file()

    @property
    def pending_sources(self) -> list[MemorySource]:
        return [source for source in self.sources if source.status == "pending"]

    @property
    def missing_sources(self) -> list[MemorySource]:
        return [source for source in self.sources if source.status == "missing"]

    @property
    def pending_count(self) -> int:
        return len(self.pending_sources)

    @property
    def missing_count(self) -> int:
        return len(self.missing_sources)

    @property
    def stale(self) -> bool:
        return bool(self.pending_count or self.missing_count)

    @property
    def status(self) -> str:
        if self.missing_count:
            return "missing"
        if self.pending_count:
            return "pending"
        if self.has_memory or self.has_reflections or self.has_legacy_reflection or self.has_legacy_improvements:
            return "current"
        return "empty"

    @property
    def status_label(self) -> str:
        return {
            "missing": "Source missing",
            "pending": "Needs walk",
            "current": "Current",
            "empty": "Empty",
        }[self.status]

    @property
    def sources_as_of(self) -> str:
        return _format_timestamp(self.sources_generated_at)

    # -- playbook -----------------------------------------------------
    @property
    def active_directives(self) -> list[dict[str, Any]]:
        return [item for item in self.directives if item.get("status") == "active"]

    @property
    def candidate_directives(self) -> list[dict[str, Any]]:
        return [item for item in self.directives if item.get("status") == "candidate"]

    @property
    def retired_directives(self) -> list[dict[str, Any]]:
        return [item for item in self.directives if item.get("status") == "retired"]

    @property
    def directive_count(self) -> int:
        return len(self.directives)

    # -- proposals ----------------------------------------------------
    @property
    def open_proposals(self) -> list[dict[str, Any]]:
        return [item for item in self.proposals if item.get("status") != "retired"]

    @property
    def proposal_count(self) -> int:
        return len(self.open_proposals)


@dataclass
class MemoryScope:
    """A scope container and the memory nodes found under it."""

    kind: str
    key: str
    name: str
    root: Path
    project_id: int | None = None
    nodes: list[MemoryNode] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.kind == "global":
            return "Global"
        if self.kind == "workspace":
            return f"Workspace · {self.name}"
        return f"Project · {self.name}"

    @property
    def pending_count(self) -> int:
        return sum(node.pending_count for node in self.nodes)

    @property
    def missing_count(self) -> int:
        return sum(node.missing_count for node in self.nodes)

    @property
    def stale(self) -> bool:
        return bool(self.pending_count or self.missing_count)

    @property
    def agent_count(self) -> int:
        return sum(1 for node in self.nodes if node.kind == "agent")

    @property
    def task_count(self) -> int:
        return sum(1 for node in self.nodes if node.kind == "task")


@dataclass
class MemoryInventory:
    """A rendered snapshot of the memory tree for one project selection."""

    project_id: int | None
    scopes: list[MemoryScope]
    warnings: list[str] = field(default_factory=list)
    generated_at: str = ""

    @property
    def nodes(self) -> list[MemoryNode]:
        return [node for scope in self.scopes for node in scope.nodes]

    @property
    def empty(self) -> bool:
        return not any(scope.nodes for scope in self.scopes)

    @property
    def totals(self) -> dict[str, int]:
        nodes = self.nodes
        return {
            "scopes": len(self.scopes),
            "nodes": len(nodes),
            "agents": sum(1 for node in nodes if node.kind == "agent"),
            "tasks": sum(1 for node in nodes if node.kind == "task"),
            "pending": sum(node.pending_count for node in nodes),
            "missing": sum(node.missing_count for node in nodes),
            "stale": sum(1 for node in nodes if node.stale),
            "directives": sum(node.directive_count for node in nodes),
            "active_directives": sum(len(node.active_directives) for node in nodes),
            "proposals": sum(node.proposal_count for node in nodes),
            "legacy": sum(1 for node in nodes if node.playbook_legacy),
            "errors": sum(len(node.errors) for node in nodes),
        }

    @property
    def stale_nodes(self) -> list[MemoryNode]:
        return sorted(
            (node for node in self.nodes if node.stale),
            key=lambda node: (-(node.missing_count + node.pending_count), node.id),
        )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _load_sources(path: Path) -> tuple[list[MemorySource], str, str]:
    """Return ``(sources, generated_at, error)`` for a manifest file."""
    if not path.is_file():
        return [], "", ""
    try:
        metadata, _body, _has_frontmatter = _schema().read_frontmatter(path)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return [], "", f"{path.name}: {exc}"

    out: list[MemorySource] = []
    for raw in metadata.get("sources") or []:
        if not isinstance(raw, dict):
            continue
        out.append(
            MemorySource(
                path=str(raw.get("path") or ""),
                type=str(raw.get("type") or ""),
                last_processed_hash=str(raw.get("last_processed_hash") or ""),
                current_hash=str(raw.get("current_hash") or ""),
                changed_chars=int(raw.get("changed_chars") or 0),
                depth=int(raw.get("depth") or 0),
                is_up_to_date=bool(raw.get("is_up_to_date", True)),
            )
        )
    return out, str(metadata.get("generated_at") or ""), ""


def _build_node(
    scope: MemoryScope,
    path: Path,
    kind: str,
    agent_pk: int | None = None,
    group_key: str = "",
) -> MemoryNode | None:
    if not _has_content(path):
        return None

    relative = path.relative_to(scope.root).as_posix() if path != scope.root else "."
    node = MemoryNode(
        id=f"memory:{scope.kind}:{scope.key}:{relative}",
        kind=kind,
        scope=scope,
        path=path,
        agent_pk=agent_pk,
        group_key=group_key,
    )

    sources, generated_at, source_error = _load_sources(node.sources_path)
    node.sources = sources
    node.sources_generated_at = generated_at
    if source_error:
        node.errors.append(source_error)

    # Legacy playbook artifacts: parse only for backward-compatible display.
    if node.has_legacy_reflection:
        try:
            playbook = _schema().load_playbook(node.legacy_reflection_path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            node.errors.append(f"{LEGACY_REFLECTION_FILENAME}: {exc}")
        else:
            node.playbook_present = bool(playbook.get("present"))
            node.playbook_legacy = bool(playbook.get("legacy"))
            node.playbook_metadata = dict(playbook.get("metadata") or {})
            node.directives = list(playbook.get("directives") or [])

    if node.has_legacy_improvements:
        try:
            ledger = _schema().load_improvements(node.legacy_improvements_path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            node.errors.append(f"{LEGACY_IMPROVEMENTS_FILENAME}: {exc}")
        else:
            node.proposals = list(ledger.get("proposals") or [])

    if node.has_memory:
        try:
            node.memory_chars = node.memory_path.stat().st_size
        except OSError:
            node.memory_chars = 0
        # Read only enough for the gist; the detail view reads the full file on
        # demand, so a large memory.md is never loaded just to render a list.
        node.memory_excerpt = _excerpt(_read_text(node.memory_path, EXCERPT_CHARS * 4))

    return node


def _resolve_agent_names(scopes: Iterable[MemoryScope]) -> None:
    pks = {
        node.agent_pk
        for scope in scopes
        for node in scope.nodes
        if node.agent_pk is not None
    }
    if not pks:
        return
    try:
        from server.models.agents.agent import AgentModel

        names = dict(
            AgentModel.objects.filter(pk__in=pks).values_list("pk", "name")
        )
    except Exception:  # pylint: disable=broad-exception-caught
        return
    for scope in scopes:
        for node in scope.nodes:
            if node.agent_pk is not None:
                node.agent_name = str(names.get(node.agent_pk) or "")


def discover(refs: Iterable[MemoryScopeRef]) -> tuple[list[MemoryScope], list[str]]:
    """Walk *refs* and return ``(scopes, warnings)``."""
    scopes: list[MemoryScope] = []
    warnings: list[str] = []
    budget = MAX_NODES

    for ref in refs:
        root = Path(ref.root).expanduser()
        if not root.is_dir():
            continue
        scope = MemoryScope(
            kind=ref.kind,
            key=ref.key,
            name=ref.name,
            root=root,
            project_id=ref.project_id,
        )

        if budget > 0:
            root_node = _build_node(scope, root, "scope")
            if root_node is not None:
                scope.nodes.append(root_node)
                budget -= 1

        for agent_dir in _iter_dirs(root / "agents"):
            if budget <= 0:
                break
            agent_pk = _int_suffix(agent_dir.name, "agent_")
            agent_node = _build_node(
                scope, agent_dir, "agent", agent_pk=agent_pk
            )
            if agent_node is not None:
                scope.nodes.append(agent_node)
                budget -= 1
            for task_dir in _iter_dirs(agent_dir / "tasks"):
                if budget <= 0:
                    break
                task_node = _build_node(
                    scope,
                    task_dir,
                    "task",
                    agent_pk=agent_pk,
                    group_key=_strip_prefix(task_dir.name, "task_"),
                )
                if task_node is not None:
                    scope.nodes.append(task_node)
                    budget -= 1

        # Keep the global scope visible even when it has no nodes yet, so the
        # overview always has a place to explain an empty tree.
        if scope.nodes or ref.kind == "global":
            scopes.append(scope)

    if budget <= 0:
        warnings.append(
            f"Memory tree truncated at {MAX_NODES} nodes; narrow the project filter."
        )

    _resolve_agent_names(scopes)
    return scopes, warnings


def build_inventory(
    project_id: int | None = None,
    refs: Iterable[MemoryScopeRef] | None = None,
) -> MemoryInventory:
    """Return the Memory UI's snapshot for *project_id*."""
    scope_list, warnings = discover(list(refs) if refs is not None else scope_refs(project_id))
    return MemoryInventory(
        project_id=project_id,
        scopes=scope_list,
        warnings=warnings,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


# ---------------------------------------------------------------------------
# Proposals across nodes
# ---------------------------------------------------------------------------


def unique_proposals(nodes: Iterable[MemoryNode]) -> list[dict[str, Any]]:
    """Return every proposal once, most specific node first.

    A lesson consolidated at the workspace, project and global layers is one
    improvement; showing it three times would make the queue look larger than
    the work.  The fingerprint is the identity the synthesizer already uses.
    """
    ordered = sorted(
        nodes,
        key=lambda node: (
            SCOPE_SPECIFICITY.get(node.scope.kind, 9),
            node.path.as_posix(),
        ),
    )
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for node in ordered:
        for proposal in node.proposals:
            fingerprint = str(proposal.get("fingerprint") or "").strip()
            if not fingerprint or fingerprint in seen:
                continue
            seen.add(fingerprint)
            out.append(
                {
                    **proposal,
                    "source": node.scope.label,
                    "node_id": node.id,
                    "node_label": node.label,
                    "project_id": node.scope.project_id,
                    "path": node.improvements_path.as_posix(),
                }
            )
    return sorted(
        out,
        key=lambda item: (
            PROPOSAL_RANK.get(str(item.get("status")), 9),
            str(item.get("kind") or ""),
            str(item.get("summary") or ""),
        ),
    )


def find_node(inventory: MemoryInventory, node_id: str) -> MemoryNode | None:
    for node in inventory.nodes:
        if node.id == node_id:
            return node
    return None


def effective_directives(
    nodes: Iterable[MemoryNode], status: str = "active", injectable_only: bool = False
) -> list[dict[str, Any]]:
    """Return directives from *nodes* once each, most specific source first.

    The playbook is resolved task → agent → workspace → project → global and
    identical fingerprints dedupe with the most specific source winning.  This
    helper applies the same rule so the UI shows what a session would actually
    be told, not four copies of the same lesson from four layers.  With
    ``injectable_only``, ``harness`` and ``memory`` routings are skipped too,
    matching the session bootstrap filter.
    """
    ordered = sorted(
        nodes,
        key=lambda node: (
            SCOPE_SPECIFICITY.get(node.scope.kind, 9),
            DIRECTIVE_LAYER.get(node.kind, 9),
            node.path.as_posix(),
        ),
    )
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for node in ordered:
        for item in node.directives:
            if status and str(item.get("status") or "") != status:
                continue
            if injectable_only and str(item.get("routing") or "").strip().lower() in NON_INJECTABLE_ROUTING:
                continue
            key = str(item.get("fingerprint") or item.get("id") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    **item,
                    "source": node.scope.label,
                    "source_kind": node.scope.kind,
                    "layer": node.kind_label,
                    "node_id": node.id,
                    "node_label": node.label,
                }
            )
    return out


def reload_node(node: MemoryNode) -> MemoryNode:
    """Re-read *node* from disk in place, keeping the same identity.

    The detail tab owns a strong reference to its node; refreshing must update
    that object rather than replace it, or the tab would silently keep the
    pre-edit data.
    """
    replacement = _build_node(
        node.scope,
        node.path,
        node.kind,
        agent_pk=node.agent_pk,
        group_key=node.group_key,
    )
    if replacement is None:
        node.sources = []
        node.sources_generated_at = ""
        node.directives = []
        node.playbook_present = False
        node.playbook_legacy = False
        node.playbook_metadata = {}
        node.proposals = []
        node.errors = []
        node.memory_excerpt = ""
        node.memory_chars = 0
        node._memory_text = None
        return node

    node.sources = replacement.sources
    node.sources_generated_at = replacement.sources_generated_at
    node.directives = replacement.directives
    node.playbook_present = replacement.playbook_present
    node.playbook_legacy = replacement.playbook_legacy
    node.playbook_metadata = replacement.playbook_metadata
    node.proposals = replacement.proposals
    node.errors = replacement.errors
    node.memory_excerpt = replacement.memory_excerpt
    node.memory_chars = replacement.memory_chars
    node._memory_text = replacement._memory_text
    return node
