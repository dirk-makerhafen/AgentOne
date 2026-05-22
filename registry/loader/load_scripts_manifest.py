from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from registry.loader.load_chain_entry import load_chain_entry
from registry.loader.load_python_entry import load_python_entry
from registry.shadow_git import get_or_init_shadow_repo
from server.models.enums.task_enums import TaskExecutionMode, TaskType
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion


def load_scripts_manifest(
    scripts_dir: Path,
    parent_project: Any = None,
    parent_agent: Any = None,
    parent_skill: Any = None,
) -> List[Tuple[TaskDefinition, TaskDefinitionVersion]]:
    """Load all entries from all ``scripts.md`` manifests found in *scripts_dir*.

    Recurses into subdirectories. Entries are processed in order so that Python
    entries are created before chain/group entries (which need to resolve child
    versions by name).

    Returns a list of ``(TaskDefinition, TaskDefinitionVersion)`` tuples.
    """
    results: List[Tuple[TaskDefinition, TaskDefinitionVersion]] = []
    for manifest_path in sorted(scripts_dir.rglob("scripts.md")):
        subdir = manifest_path.parent
        with open(manifest_path, encoding="utf-8") as f:
            manifest: dict = yaml.safe_load(f) or {}

        commit = get_or_init_shadow_repo(subdir)
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
            print(item)
            entries.append(item)
    return entries


def _load_script_entry(
    entry: Dict[str, Any],
    scripts_dir: Path,
    commit: str,
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
    print("_load_script_entry", entry)

    if task_execution_mode == TaskExecutionMode.FUNCTION:
        load_python_entry(
            entry, scripts_dir, commit, task_type, task_execution_mode,
            name, parent_project, parent_agent, parent_skill, existing_results,
        )
    elif task_execution_mode in (TaskExecutionMode.CHAIN, TaskExecutionMode.GROUP):
        load_chain_entry(
            entry, commit, task_type, task_execution_mode, name,
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
