from pathlib import Path
import yaml
from registry.loader.load_chain_entry import load_chain_entry
from registry.loader.load_python_entry import load_python_entry
from registry.shadow_git import get_or_init_shadow_repo
from server.models.enums.task_enums import TaskExecutionMode, TaskType


def load_scripts_manifest(scripts_dir: Path, parent_project=None, parent_agent=None, parent_skill=None):
    """
    Load all entries from all scripts.md manifests found in the given
    directory (recurses into subdirectories).

    Processes entries in order so python entries are created before chain
    entries (which need to resolve child versions by name).

    Returns list of (TaskDefinition, TaskDefinitionVersion) tuples.
    """
    results = []
    for manifest_path in sorted(scripts_dir.rglob("scripts.md")):
        subdir = manifest_path.parent
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f) or {}

        commit = get_or_init_shadow_repo(subdir)
        entries = _collect_manifest_entries(manifest)
        
        for entry in entries:
            _load_script_entry(entry, subdir, commit, results, parent_project, parent_agent, parent_skill)

    return results


def _collect_manifest_entries(manifest):
    """Flatten tools/tasks/commands from manifest into ordered list."""
    entries = []
    for key, ttype in [("tools", TaskType.TOOL), ("tasks", TaskType.TASK), ("commands", TaskType.COMMAND)]:
        for item in manifest.get(key, []):
            item["task_type"] = ttype
            for fkey, fenum in _ENTRY_TYPE_TO_EXECUTION_MODE.items():
                if fkey in item:
                    item["task_execution_mode"] = fenum
                    break
            print(item)
            entries.append(item)
    return entries



def _load_script_entry(entry, scripts_dir, commit, existing_results, parent_project, parent_agent, parent_skill):
    task_type = entry["task_type"]
    task_execution_mode = entry["task_execution_mode"]
    name = entry["name"]
    print("_load_script_entry", entry)

    if task_execution_mode == TaskExecutionMode.FUNCTION:
        load_python_entry(entry, scripts_dir, commit, task_type, task_execution_mode, name, parent_project, parent_agent, parent_skill, existing_results)
    elif task_execution_mode in (TaskExecutionMode.CHAIN, TaskExecutionMode.GROUP):
        load_chain_entry(entry, commit, task_type, task_execution_mode, name, parent_project, parent_agent, parent_skill, existing_results)
    else:
        raise ValueError(f"Unknown execution mode '{task_execution_mode}' for '{name}'")



_ENTRY_TYPE_TO_EXECUTION_MODE = {
    "function": TaskExecutionMode.FUNCTION,
    "script": TaskExecutionMode.SCRIPT,
    "chain": TaskExecutionMode.CHAIN,
    "group": TaskExecutionMode.GROUP,
    "chord": TaskExecutionMode.CHORD,
    "map": TaskExecutionMode.MAP,
}