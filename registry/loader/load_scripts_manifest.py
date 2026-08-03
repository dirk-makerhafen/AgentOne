from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
import frontmatter
from registry.install_repo import InstallRepo
from registry.loader.load_chain_entry import load_chain_entry
from registry.loader.load_python_entry import load_python_entry
from registry.loader.load_script_entry import load_script_entry
from server.models.enums.task_enums import TaskExecutionMode, TaskType
from server.models.tasks.scripts_generation import ScriptsGeneration
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion


def load_scripts_manifest(
    scripts_dir: Path,
    install_repo: InstallRepo,
    parent_project: Any = None,
    parent_agent: Any = None,
    parent_skill: Any = None,
    details: list | None = None,
) -> List[Tuple[TaskDefinition, TaskDefinitionVersion]]:
    """Load all entries from all ``scripts.md`` manifests found in *scripts_dir*.

    Recurses into subdirectories. Entries are loaded in two passes so chain /
    group / map entries can reference standalone functions/scripts from *any*
    ``scripts.md`` under *scripts_dir*, independent of directory order:

    1. Standalone entries (``function`` / ``script``) are loaded first.
    2. Chain / group / map entries are resolved afterwards, re-waved until
       all step references resolve (nested chains included). A wave that makes
       no progress raises with a list of the unresolved steps.

    Version identifiers are deterministic git tree SHAs from *install_repo*.

    For global scripts (no parent), a ``ScriptsGeneration`` is created (or
    reused) to track which task definitions are current.

    Returns a list of ``(TaskDefinition, TaskDefinitionVersion)`` tuples.
    """
    is_global = parent_project is None and parent_agent is None and parent_skill is None
    results: List[Tuple[TaskDefinition, TaskDefinitionVersion]] = []

    # For global scripts, create a fresh ScriptsGeneration for this
    # reload, so all current tasks share the same generation and the
    # latest generation always reflects the current manifest state.
    # Old generations (from prior reloads) are left in place so that
    # orphaned/removed tasks automatically fall out of scope.
    parent_generation = None
    if is_global:
        root_commit = install_repo.tree_sha(scripts_dir) or ""
        parent_generation = ScriptsGeneration.objects.create(
            commit=root_commit
        )

    # Collect every entry from every scripts.md before loading, so a chain in
    # one file can reference a task defined in any other file.
    collected: List[Tuple[Dict[str, Any], Path, str | None, Path]] = []
    for manifest_path in sorted(scripts_dir.rglob("scripts.md")):
        subdir = manifest_path.parent
        manifest = frontmatter.load(manifest_path)
        if len(manifest.keys()) == 0:
            if len(manifest_path.read_text().strip()) == 0:
                # empty file
                return []
            raise Exception(f"Failed to load frontmatter from {manifest_path}, did you forget closing \\n---\\n\\n?")
        commit = install_repo.tree_sha(subdir)
        for entry in _collect_manifest_entries(manifest):
            collected.append((entry, subdir, commit, manifest_path))

    # Pass 1 — standalone functions/scripts (chains depend on these).
    deferred: List[Tuple[Dict[str, Any], Path, str | None, Path]] = []
    for entry, subdir, commit, manifest_path in collected:
        if entry["task_execution_mode"] in (
            TaskExecutionMode.FUNCTION,
            TaskExecutionMode.SCRIPT,
        ):
            _load_script_entry(
                entry, subdir, commit, results,
                parent_project, parent_agent, parent_skill, details,
                parent_generation=parent_generation,
                manifest_path=manifest_path,
            )
        else:
            deferred.append((entry, subdir, commit, manifest_path))

    # Pass 2 — chain / group / map entries, re-waved until every step
    # reference resolves (chains may reference other chains).
    while deferred:
        still_deferred: List[Tuple[Dict[str, Any], Path, str | None, Path]] = []
        progressed = False
        for entry, subdir, commit, manifest_path in deferred:
            try:
                _load_script_entry(
                    entry, subdir, commit, results,
                    parent_project, parent_agent, parent_skill, details,
                    parent_generation=parent_generation,
                    manifest_path=manifest_path,
                )
                progressed = True
            except LookupError:
                still_deferred.append((entry, subdir, commit, manifest_path))
        if not progressed:
            raise _build_unresolved_chain_error(still_deferred, results)
        deferred = still_deferred

    return results


def _build_unresolved_chain_error(
    deferred: List[Tuple[Dict[str, Any], Path, str | None, Path]],
    results: List[Tuple[TaskDefinition, TaskDefinitionVersion]],
) -> LookupError:
    """Build a detailed error listing every chain step that never resolved."""
    defined = {td.name for td, _ in results}
    lines: List[str] = []
    for entry, _, _, manifest_path in deferred:
        steps = entry.get("chain") or entry.get("group") or entry.get("map") or []
        missing = [s for s in steps if s not in defined]
        lines.append(f"  - '{entry['name']}' in {manifest_path}: missing step(s) {missing}")
    return LookupError(
        "Could not resolve chain step(s) (no dependency wave made progress):\n"
        + "\n".join(lines)
        + "\nEach step must be defined as a tool/task/command (function or "
          "script) in a scripts.md under this scripts directory. Missing "
          "steps are likely typos, renamed definitions, or names that exist "
          "only outside this scripts directory."
    )


def _collect_manifest_entries(manifest: dict) -> List[Dict[str, Any]]:
    """Flatten tools / tasks / commands from *manifest* into an ordered list.

    Each entry is annotated with ``task_type`` and ``task_execution_mode``.
    """
    entries: List[Dict[str, Any]] = []
    group_name = manifest.get("group", "")
    for key, ttype in [
        ("tools", TaskType.TOOL),
        ("tasks", TaskType.TASK),
        ("commands", TaskType.COMMAND),
    ]:
        for item in manifest.get(key, []):
            item["task_type"] = ttype
            for fkey, fenum in _ENTRY_TYPE_TO_EXECUTION_MODE.items():
                if fkey in item:
                    item["task_execution_mode"] = fenum
                    break
            item["group_name"] = group_name
            entries.append(item)
    return entries


def _load_script_entry(
    entry: Dict[str, Any],
    scripts_dir: Path,
    commit: str |None,
    existing_results: List[Tuple[TaskDefinition, TaskDefinitionVersion]],
    parent_project: Any,
    parent_agent: Any,
    parent_skill: Any,
    details: list | None = None,
    parent_generation: ScriptsGeneration | None = None,
    manifest_path: Path | None = None,
) -> None:
    """Dispatch a single manifest entry to the appropriate loader.

    Supports ``FUNCTION``, ``SCRIPT``, ``CHAIN``, ``GROUP``, and ``MAP``.
    """
    task_type: TaskType = entry["task_type"]
    task_execution_mode: TaskExecutionMode = entry["task_execution_mode"]
    name: str = entry["name"]
    group_name: str = entry.get("group_name", scripts_dir.name)

    if task_execution_mode == TaskExecutionMode.FUNCTION:
        load_python_entry(
            entry, scripts_dir, commit, task_type, task_execution_mode,
            name, group_name, parent_project, parent_agent, parent_skill, existing_results, details,
            parent_generation=parent_generation,
        )
    elif task_execution_mode == TaskExecutionMode.SCRIPT:
        load_script_entry(
            entry, scripts_dir, commit, task_type, task_execution_mode,
            name, group_name, parent_project, parent_agent, parent_skill, existing_results, details,
            parent_generation=parent_generation,
        )
    elif task_execution_mode in (TaskExecutionMode.CHAIN, TaskExecutionMode.GROUP, TaskExecutionMode.MAP):
        load_chain_entry(
            entry, commit, task_type, task_execution_mode, name, group_name,
            parent_project, parent_agent, parent_skill, existing_results, details,
            parent_generation=parent_generation,
            manifest_path=manifest_path,
        )
    else:
        raise ValueError(
            f"Unknown execution mode '{task_execution_mode}' for '{name}'"
        )


_ENTRY_TYPE_TO_EXECUTION_MODE: Dict[str, TaskExecutionMode] = {
    "function": TaskExecutionMode.FUNCTION,
    "script": TaskExecutionMode.SCRIPT,
    "chain": TaskExecutionMode.CHAIN,
    "group": TaskExecutionMode.GROUP,
    "map": TaskExecutionMode.MAP,
}
