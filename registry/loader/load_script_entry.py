from pathlib import Path
from typing import Any, List, Tuple

from registry.loader.utils import build_version_kwargs
from server.models.enums.task_enums import TaskExecutionMode, TaskType
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion


def load_script_entry(
    entry: dict,
    scripts_dir: Path,
    commit: str | None,
    task_type: TaskType,
    task_execution_mode: TaskExecutionMode,
    name: str,
    group_name: str,
    parent_project: Any,
    parent_agent: Any,
    parent_skill: Any,
    existing_results: List[Tuple[TaskDefinition, TaskDefinitionVersion]],
    details: list | None = None,
) -> None:
    """Load a script/binary entry from a scripts.md manifest.

    Unlike ``load_python_entry``, this does *not* import the file or
    introspect a function — the file is treated as an arbitrary executable.
    Schema and description are taken from the entry metadata if provided.
    """
    file_path = scripts_dir / entry["script"]

    if not file_path.exists():
        raise FileNotFoundError(f"Script file not found: {file_path}")

    description: str = entry.get("description", "")
    schema: dict = entry.get("schema", {})

    kw = build_version_kwargs(
        entry, description, schema, commit, file_path,
        task_type, task_execution_mode,
    )
    task_def, _ = TaskDefinition.objects.get_or_create(
        parent_skill=parent_skill,
        parent_agent=parent_agent,
        parent_project=parent_project,
        name=name,
        group_name=group_name,
    )
    task_version, created = TaskDefinitionVersion.objects.get_or_create(
        task_definition=task_def, **kw,
    )
    if created:
        TaskDefinition.objects.filter(pk=task_def.pk).update(
            latest_task_version=task_version
        )
    if details is not None:
        details.append({"name": name, "type": "script", "action": "created" if created else "up to date"})
    existing_results.append((task_def, task_version))
