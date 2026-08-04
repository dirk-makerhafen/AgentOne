from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from registry.loader.utils import build_version_kwargs
from server.models.enums.task_enums import TaskExecutionMode, TaskType
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion


def load_chain_entry(
    entry: dict,
    commit: str|None,
    task_type: TaskType,
    task_execution_mode: TaskExecutionMode,
    name: str,
    group_name:str,
    parent_project: Any,
    parent_agent: Any,
    parent_skill: Any,
    existing_results: List[Tuple[TaskDefinition, TaskDefinitionVersion]],
    details: list | None = None,
    parent_generation: Any = None,
    manifest_path: Path | None = None,
) -> None:
    """Load a chain/group entry from a scripts.md manifest.

    Resolves step names from *existing_results* (must appear earlier in the
    manifest), builds the child version relationships, and persists both the
    ``TaskDefinition`` and ``TaskDefinitionVersion``.
    """
    step_names: List[str] = entry.get("chain") or entry.get("group") or entry.get("map") or []

    child_versions: List[TaskDefinitionVersion] = []
    for step_name in step_names:
        child = _find_task_version(step_name, existing_results)
        if child is None:
            available = ", ".join(td.name for td, _ in existing_results) or "(none loaded yet)"
            raise LookupError(
                f"Chain step '{step_name}' not found for task '{name}' "
                f"({manifest_path or 'unknown scripts.md'}): it must be "
                f"defined as a standalone tool/task/command (function or "
                f"script) in a scripts.md under this scripts directory. "
                f"Tasks already defined: [{available}]"
            )
        child_versions.append(child)

    description = entry.get(
        "description",
        f"{task_type.lower()} {task_execution_mode.lower()}: {' → '.join(step_names)}",
    )

    schema: Dict[str, Any] = {"steps": step_names}

    kw = build_version_kwargs(
        entry, description, schema, commit, path=None,
        task_type=task_type, task_execution_mode=task_execution_mode,
    )
    access_posture = entry.get("access")
    if access_posture not in ("read", "write"):
        access_posture = None
    task_def, _ = TaskDefinition.objects.get_or_create(
        parent_skill=parent_skill,
        parent_agent=parent_agent,
        parent_project=parent_project,
        name=name,
        group_name=group_name,
    )
    if task_def.access_posture != access_posture:
        TaskDefinition.objects.filter(pk=task_def.pk).update(
            access_posture=access_posture
        )
        task_def.refresh_from_db()
    if parent_generation is not None and task_def.parent_generation_id != parent_generation.pk:
        TaskDefinition.objects.filter(pk=task_def.pk).update(
            parent_generation=parent_generation
        )
    task_version, created = TaskDefinitionVersion.objects.get_or_create(
        task_definition=task_def, **kw,
    )
    if created:
        task_version.child_tasks.set(child_versions)
        TaskDefinition.objects.filter(pk=task_def.pk).update(
            latest_task_version=task_version
        )
    if details is not None:
        details.append({"name": name, "type": "script", "action": "created" if created else "up to date"})
    existing_results.append((task_def, task_version))


def _find_task_version(
    name: str,
    results: List[Tuple[TaskDefinition, TaskDefinitionVersion]],
) -> Optional[TaskDefinitionVersion]:
    """Return the latest ``TaskDefinitionVersion`` by task name in *results*.

    Returns ``None`` when no match is found.
    """
    for td, tv in results:
        if td.name == name:
            return tv
    return None
