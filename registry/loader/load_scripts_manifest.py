from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
import frontmatter
from registry.install_repo import InstallRepo
from registry.loader.load_chain_entry import load_chain_entry
from registry.loader.load_python_entry import load_python_entry
from server.models.enums.task_enums import TaskExecutionMode, TaskType
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion


def load_scripts_manifest(
    scripts_dir: Path,
    install_repo: InstallRepo,
    parent_project: Any = None,
    parent_agent: Any = None,
    parent_skill: Any = None,
) -> List[Tuple[TaskDefinition, TaskDefinitionVersion]]:
    """Load all entries from all ``scripts.md`` manifests found in *scripts_dir*.

    Recurses into subdirectories. Entries are processed in order so that Python
    entries are created before chain/group entries (which need to resolve child
    versions by name).

    Version identifiers are deterministic git tree SHAs from *install_repo*.

    Returns a list of ``(TaskDefinition, TaskDefinitionVersion)`` tuples.
    """
    results: List[Tuple[TaskDefinition, TaskDefinitionVersion]] = []
    for manifest_path in sorted(scripts_dir.rglob("scripts.md")):
        subdir = manifest_path.parent
        manifest = frontmatter.load(manifest_path)

        commit = install_repo.tree_sha(subdir)
        entries = _collect_manifest_entries(manifest)

        for entry in entries:
            _load_script_entry(
                entry, subdir, commit, results,
                parent_project, parent_agent, parent_skill,
            )

    return results


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
            print(item)
            entries.append(item)
    print("RETURHN")
    return entries


def _load_script_entry(
    entry: Dict[str, Any],
    scripts_dir: Path,
    commit: str |None,
    existing_results: List[Tuple[TaskDefinition, TaskDefinitionVersion]],
    parent_project: Any,
    parent_agent: Any,
    parent_skill: Any,
) -> None:
    """Dispatch a single manifest entry to the appropriate loader.

    Supports ``FUNCTION``, ``CHAIN``, and ``GROUP`` execution modes.
    """
    task_type: TaskType = entry["task_type"]
    task_execution_mode: TaskExecutionMode = entry["task_execution_mode"]
    name: str = entry["name"]
    group_name: str = entry.get("group_name", scripts_dir.name)
    print("_load_script_entry", entry)

    if task_execution_mode == TaskExecutionMode.FUNCTION:
        load_python_entry(
            entry, scripts_dir, commit, task_type, task_execution_mode,
            name, group_name, parent_project, parent_agent, parent_skill, existing_results,
        )
    elif task_execution_mode in (TaskExecutionMode.CHAIN, TaskExecutionMode.GROUP, TaskExecutionMode.MAP):
        load_chain_entry(
            entry, commit, task_type, task_execution_mode, name, group_name,
            parent_project, parent_agent, parent_skill, existing_results,
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
    "chord": TaskExecutionMode.CHORD,
    "map": TaskExecutionMode.MAP,
}
