
from registry.loader.utils import build_version_kwargs
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion


def load_chain_entry(entry, commit, task_type, task_execution_mode, name, parent_project, parent_agent, parent_skill, existing_results):
    step_names = entry.get("chain") or entry.get("group") or []
    child_versions = []
    for step_name in step_names:
        child = _find_task_version(step_name, existing_results)
        if child is None:
            raise LookupError(f"Chain step '{step_name}' not found in existing results (must appear earlier in scripts.md)")
        child_versions.append(child)

    description = entry.get("description", f"{task_type.lower()} {task_execution_mode.lower()}: {' → '.join(step_names)}")
                        
    schema = {"steps": step_names}

    kw = build_version_kwargs(entry, description, schema, commit, path=None, task_type=task_type, task_execution_mode=task_execution_mode)
    task_def, _ = TaskDefinition.objects.get_or_create(parent_skill=parent_skill, parent_agent=parent_agent, parent_project=parent_project, name=name)
    task_version, created = TaskDefinitionVersion.objects.get_or_create(task_definition=task_def, **kw)
    if created:
        task_version.child_tasks.set(child_versions)
        TaskDefinition.objects.filter(pk=task_def.pk).update(latest_task_version=task_version)
    existing_results.append((task_def, task_version))


def _find_task_version(name, results):
    """Find the latest TaskDefinitionVersion by task name in results."""
    for td, tv in results:
        if td.name == name:
            return tv
    return None
