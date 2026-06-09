from pathlib import Path
import textwrap
from typing import Any, Dict, List, Optional

import frontmatter
import yaml

from server.models.enums.task_enums import TaskExecutionMode, TaskType


def _toposort_agents(paths: List[Path]) -> List[Path]:
    """Topologically sort agent files so parents load before children.

    Reads ``extends`` and ``subagents`` from each file's YAML
    frontmatter, builds a dependency graph, and returns paths in
    dependency order (roots first).
    """
    # Build graph: name -> list of dependency names and name -> path
    graph: Dict[str, List[str]] = {}
    name_to_path: Dict[str, Path] = {}

    for p in paths:
        try:
            post = frontmatter.loads(p.read_text(encoding="utf-8"))
            meta = post.metadata if isinstance(post, frontmatter.Post) else (post or {})
            name = meta.get("name", p.parent.name)

            # Collect all dependency names (extends + subagents)
            deps: List[str] = []

            extends = meta.get("extends") or []
            if isinstance(extends, str):
                extends = [e.strip() for e in extends.split(",") if e.strip()]
            deps.extend(extends)

            subagents = meta.get("subagents") or []
            if isinstance(subagents, list):
                for sa in subagents:
                    if isinstance(sa, dict):
                        sa_name = sa.get("name", "")
                        if sa_name and sa_name != name:  # skip self-ref
                            deps.append(sa_name)
                    elif isinstance(sa, str):
                        if sa != name:
                            deps.append(sa)

            graph[name] = [d for d in deps if d]
            name_to_path[name] = p
        except (yaml.YAMLError, Exception):
            # fallback: use directory name as agent name, no parents
            name = p.parent.name
            graph[name] = []
            name_to_path[name] = p

    # ── Kahn's algorithm ──────────────────────────────────────────────
    # Build reverse adjacency: dep -> [names that depend on dep]
    dependents: Dict[str, List[str]] = {}
    for name, deps in graph.items():
        for dep in deps:
            if dep in graph:
                dependents.setdefault(dep, []).append(name)

    in_degree: Dict[str, int] = {}
    for name in graph:
        in_degree[name] = sum(1 for d in graph[name] if d in graph)

    queue = [n for n, deg in in_degree.items() if deg == 0]
    sorted_names: List[str] = []

    while queue:
        node = queue.pop(0)
        sorted_names.append(node)
        for dependent in dependents.get(node, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Append any nodes missed due to cycles
    for name in in_degree:
        if name not in sorted_names:
            sorted_names.append(name)

    result: List[Path] = [name_to_path[n] for n in sorted_names if n in name_to_path]
    return result


def find_agent_md_files(root_dir: Path) -> List[Path]:
    """Recursively find agent.md files, deduplicating nested paths.

    Returns files in dependency order so that parent agents are loaded
    before agents that extend them.
    """
    paths = sorted(root_dir.glob("**/agent.md"), key=lambda p: len(p.parts))
    deduped: List[Path] = []
    for p in paths:
        parent_str = p.parent.as_posix()
        if not any(parent_str.startswith(other.parent.as_posix()) for other in deduped):
            deduped.append(p)
    return _toposort_agents(deduped)


def build_version_kwargs(
    entry: dict,
    description: str,
    schema: dict,
    commit: str|None,
    path: Optional[Path],
    task_type: TaskType,
    task_execution_mode: TaskExecutionMode,
) -> Dict[str, Any]:
    """Build ``TaskDefinitionVersion`` filter kwargs from a manifest entry.

    Returns a dict suitable for ``get_or_create`` that includes the function
    schema, type info, and any optional overrides (e.g. retry config).
    """
    kw: Dict[str, Any] = {
        "description": textwrap.dedent(description),
        "function_schema": schema or {},
        "task_type": task_type,
        "task_execution_mode": task_execution_mode,
        "function_name": entry.get("function", "") or "",
        "path": path.as_posix() if path else "",
        "commit": commit,
        "bound": entry.get("bound", False),
    }
    for opt_field in (
        "requires_approval",
        "max_retries",
        "retry_delay",
        "retry_requires_approval",
        "priority",
        "thinking",
    ):
        val = entry.get(opt_field)
        if val is not None:
            kw[opt_field] = val
    return kw
