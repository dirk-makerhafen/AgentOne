"""
Loaders for scripts.md, skill.md, and agent.md manifests.

Each loader reads the manifest file, resolves dependencies (scripts → tasks,
skills → scripts → tasks, agents → skills + scripts + subagents), creates
the corresponding DB models, and returns versioned objects.

Versioning uses a shadow git repo per manifest folder for content hashing.
"""

import importlib.util
import inspect
import textwrap
from pathlib import Path

import yaml
import frontmatter

from registry.shadow_git import get_or_init_shadow_repo
from registry.utils import generate_schema_for_function, get_ai_model
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.content import GenericContent
from server.models.enums.task_enums import TaskExecutionMode, TaskType
from server.models.project import Project
from server.models.settings import SettingsModel
from server.models.skills.skill import SkillModel, SkillModelVersion
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion


# ---------------------------------------------------------------------------
# Scripts loader (scripts.md) — tasks, tools, commands
# ---------------------------------------------------------------------------

_ENTRY_TYPE_TO_EXECUTION_MODE = {
    "function": TaskExecutionMode.FUNCTION,
    "script": TaskExecutionMode.SCRIPT,
    "chain": TaskExecutionMode.CHAIN,
    "group": TaskExecutionMode.GROUP,
    "chord": TaskExecutionMode.CHORD,
    "map": TaskExecutionMode.MAP,
}

def load_scripts_manifest(scripts_dir: Path, parent_project=None,
                          parent_agent=None, parent_skill=None):
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
            _load_script_entry(entry, subdir, commit, results,
                               parent_project, parent_agent, parent_skill)

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


def _load_script_entry(entry, scripts_dir, commit, existing_results,
                       parent_project, parent_agent, parent_skill):
    task_type = entry["task_type"]
    task_execution_mode = entry["task_execution_mode"]
    name = entry["name"]
    print("_load_script_entry", entry)
    if task_execution_mode == TaskExecutionMode.FUNCTION:
        _load_python_entry(entry, scripts_dir, commit, task_type,
                           task_execution_mode, name,
                           parent_project, parent_agent, parent_skill,
                           existing_results)
    elif task_execution_mode in (TaskExecutionMode.CHAIN, TaskExecutionMode.GROUP):
        _load_chain_entry(entry, commit, task_type, task_execution_mode,
                          name, parent_project, parent_agent, parent_skill,
                          existing_results)
    else:
        raise ValueError(
            f"Unknown execution mode '{task_execution_mode}' for '{name}'"
        )


def _load_python_entry(entry, scripts_dir, commit, task_type,
                       task_execution_mode, name,
                       parent_project, parent_agent, parent_skill,
                       existing_results):
    file_path = scripts_dir / entry["file"]
    function_name = entry["function"]
    bound = entry.get("bound", False)

    if not file_path.exists():
        raise FileNotFoundError(f"Script file not found: {file_path}")

    spec = importlib.util.spec_from_file_location(
        f"_manifest_{name}", file_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, function_name, None)
    if func is None:
        raise AttributeError(f"Function '{function_name}' not in {file_path}")

    description, schema = generate_schema_for_function(func)

    if bound:
        _strip_bound_param(schema)

    kw = _build_version_kwargs(entry, description, schema, commit, file_path, task_type, task_execution_mode)
    task_def, _ = TaskDefinition.objects.get_or_create( parent_skill=parent_skill, parent_agent=parent_agent, parent_project=parent_project, name=name)
    task_version, created = TaskDefinitionVersion.objects.get_or_create(task_definition=task_def, **kw)
    if created:
        TaskDefinition.objects.filter(pk=task_def.pk).update(latest_task_version=task_version)
    existing_results.append((task_def, task_version))


def _load_chain_entry(entry, commit, task_type, task_execution_mode, name,
                      parent_project, parent_agent, parent_skill,
                      existing_results):
    step_names = entry.get("chain") or entry.get("group") or []
    child_versions = []
    for step_name in step_names:
        child = _find_task_version(step_name, existing_results)
        if child is None:
            raise LookupError(
                f"Chain step '{step_name}' not found in existing results "
                f"(must appear earlier in scripts.md)"
            )
        child_versions.append(child)

    description = entry.get("description", f"{task_type.lower()} "
                                           f"{task_execution_mode.lower()}: "
                                           f"{' → '.join(step_names)}")
    schema = {"steps": step_names}

    kw = _build_version_kwargs(entry, description, schema, commit, path=None, task_type=task_type, task_execution_mode=task_execution_mode)
    task_def, _ = TaskDefinition.objects.get_or_create(parent_skill=parent_skill, parent_agent=parent_agent, parent_project=parent_project, name=name)
    task_version, created = TaskDefinitionVersion.objects.get_or_create(task_definition=task_def, **kw)
    if created:
        task_version.child_tasks.set(child_versions)
        TaskDefinition.objects.filter(pk=task_def.pk).update(latest_task_version=task_version)
    existing_results.append((task_def, task_version))


# ---------------------------------------------------------------------------
# Skill loader (skill.md)
# ---------------------------------------------------------------------------

def load_skill_manifest(skill_md_path: Path, parent_project=None,
                        parent_agent=None):
    manifest = frontmatter.load(skill_md_path)
    skill_dir = skill_md_path.parent
    commit = get_or_init_shadow_repo(skill_dir)

    skill, _ = SkillModel.objects.get_or_create(
        name=manifest.get("name"),
        parent_agent=parent_agent,
        parent_project=parent_project,
    )

    skill_version, created = SkillModelVersion.objects.get_or_create(
        skill=skill,
        description=manifest.get("description", ""),
        path=skill_md_path.as_posix(),
        commit=commit,
    )
    if created:
        SkillModel.objects.filter(pk=skill.pk).update(
            latest_skill_version=skill_version
        )

    # Load scripts from scripts/ subfolder
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        load_scripts_manifest(
            scripts_dir,
            parent_project=parent_project,
            parent_agent=parent_agent,
            parent_skill=skill,
        )

    return skill, skill_version


# ---------------------------------------------------------------------------
# Agent loader (agent.md)
# ---------------------------------------------------------------------------

def load_agent_manifest(agent_md_path: Path, parent_project=None,
                        parent_agent=None, parent_skill=None):
    print("load_agent_manifest", agent_md_path)
    manifest = frontmatter.load(agent_md_path)
    agent_dir = agent_md_path.parent
    commit = get_or_init_shadow_repo(agent_dir)

    def get_list(name):
        val = manifest.get(name)
        if val is None:
            return val
        if isinstance(val, str):
            val = [x.strip() for x in val.split(",") if x.strip()]
        return val

    # Agent model (handle oldName rename)
    old_name = manifest.get("oldName")
    name = manifest.get("name")
    if old_name:
        agent = AgentModel.objects.get(
            name=old_name,
            parent_project=parent_project,
            parent_agent=parent_agent,
            parent_skill=parent_skill,
        )
        agent.name = name
        agent.save()
    else:
        agent, _ = AgentModel.objects.get_or_create(
            name=name,
            parent_project=parent_project,
            parent_agent=parent_agent,
            parent_skill=parent_skill,
        )

    # Load child scripts
    defined_tasks = []
    scripts_dir = agent_dir / "scripts"
    if scripts_dir.is_dir():
        defined_tasks = load_scripts_manifest(
            scripts_dir,
            parent_project=parent_project,
            parent_agent=agent,
        )
    print("defined_tasks", defined_tasks)
    # Load child skills
    defined_skills = []
    skills_dir = agent_dir / "skills"
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("**/skill.md")):
            skill, sv = load_skill_manifest(
                skill_md,
                parent_project=parent_project,
                parent_agent=agent,
            )
            defined_skills.append((skill, sv))

    # Load child subagents
    defined_subagents = []
    agents_dir = agent_dir / "agents"
    if agents_dir.is_dir():
        for sub_md in _find_agent_md_files(agents_dir):
            subagent, sav = load_agent_manifest(sub_md, parent_project=parent_project, parent_agent=agent)
            defined_subagents.append((subagent, sav))

    # Build SettingsModel
    aimodel = get_ai_model(manifest.get("model"))
    extend_agent_names = get_list("extends") or []

    settings_kwargs = {
        "aimodel": aimodel,
        "max_retries": manifest.get("maxRetries"),
        "max_turns": manifest.get("maxTurns"),
        "max_unattended_turns": manifest.get("maxUnattendedTurns"),
        "max_history_messages": manifest.get("maxHistoryMessages"),
        "scheduler_strategy": manifest.get("schedulerStrategy"),
        "tool_call_syntax": manifest.get("toolCallSyntax"),
        "reasoning_effort": manifest.get("reasoningEffort"),
        "commandNames": get_list("commands"),
        "disallowedCommandNames": get_list("disallowedCommands"),
        "taskNames": get_list("tasks"),
        "disallowedTaskNames": get_list("disallowedTasks"),
        "toolNames": get_list("tools"),
        "disallowedToolNames": get_list("disallowedTools"),
        "skillNames": get_list("skills"),
        "disallowedSkillNames": get_list("disallowedSkills"),
        "priority": manifest.get("priority"),
        "thinking": manifest.get("thinking"),
        "task_prompt": GenericContent.from_text(
            (manifest.get("task_prompt") or "").strip()
        ),
        "system_prompt": GenericContent.from_text(
            (manifest.content or "").strip()
        ),
        "commit": commit,
    }
    settings_kwargs = {k: v for k, v in settings_kwargs.items() if v is not None}
    settings, _ = SettingsModel.objects.get_or_create(**settings_kwargs)

    # Resolve extends
    extend_versions = []
    for ext_name in extend_agent_names:
        ext_agent = AgentModel.objects.get(name=ext_name)
        if ext_agent.latest_agent_version:
            extend_versions.append(ext_agent.latest_agent_version)
        else:
            raise Exception(f"no latest found for {ext_agent}")
    # Build hash from all dependencies
    dep_pks = (
        [str(v.pk) for v in extend_versions]
        + [s for s in extend_agent_names if s]
        + [str(sv.pk) for _, sv in defined_skills]
        + [str(tv.pk) for _, tv in defined_tasks]
        + [str(sav.pk) for _, sav in defined_subagents]
    )
    print("EXTENDS",agent_md_path, extend_versions)
    import hashlib
    hash_str = "_".join(sorted(set(dep_pks)))
    content_hash = hashlib.sha1(hash_str.encode()).hexdigest()

    current_vn = 1
    if agent.latest_agent_version:
        current_vn = agent.latest_agent_version.version_number

    agent_version, created = AgentVersionModel.objects.get_or_create(
        agent=agent,
        description=manifest.get("description", ""),
        extends_agent_names=extend_agent_names,
        commit=commit,
        agent_settings=settings,
        hash=content_hash,
    )
    if created:
        agent_version.extends_agent_versions.set(extend_versions)
        AgentVersionModel.objects.filter(pk=agent_version.pk).update(version_number=current_vn + 1)
        AgentModel.objects.filter(pk=agent.pk).update(latest_agent_version=agent_version)
        agent_version.defined_skill_versions.set([sv for _, sv in defined_skills])
        agent_version.defined_task_versions.set([tv for _, tv in defined_tasks])
        agent_version.defined_subagent_versions.set([sav for _, sav in defined_subagents])

    resolve_agent_version_tasks(agent_version)

    return agent, agent_version


# ---------------------------------------------------------------------------
# Pass 2: Resolve tasks for agent versions
# ---------------------------------------------------------------------------

def resolve_agent_version_tasks(agent_version: AgentVersionModel):
    """Resolve the tools:/tasks:/commands: name lists from the agent's
    SettingsModel into TaskDefinitionVersion objects and set tasks.

    Looks up versions in order of precedence:
      1. own defined_task_versions
      2. extends chain (parent agent versions)
      3. global (no parent_agent, no parent_project, no parent_skill)
    """
    settings = agent_version.agent_settings
    if not settings:
        return

    rt = agent_version.get_runtime()
    resolved = set()

    for names in [rt.allowedTaskNames, rt.allowedToolNames, rt.allowedCommandNames]:
        print("FOOOOO23", names)
        if not names:
            return

        for name in names:
            print("slook", name)

            tdv = agent_version.defined_task_versions.filter(task_definition__name=name).first()
            if tdv:
                resolved.add(tdv.pk)
                continue
            for ext in agent_version.extends_agent_versions.all():
                print("ETCENDS", ext, ext.defined_task_versions.all())
                tdv = ext.defined_task_versions.filter(task_definition__name=name).first()
                if tdv:
                    resolved.add(tdv.pk)
                    break
            else:
                print("SEARCH GLOBAL")
                tdv = TaskDefinition.objects.filter(name=name, parent_agent__isnull=True, parent_project__isnull=True, parent_skill__isnull=True).first().latest_task_version
                print("found", tdv)
                resolved.add(tdv.pk)
    if not resolved:
        raise Exception(f"not found {name}")
    agent_version.task_versions.set(
        TaskDefinitionVersion.objects.filter(pk__in=resolved)
    )



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_version_kwargs(entry, description, schema, commit, path,
                          task_type, task_execution_mode):
    """Build TaskDefinitionVersion filter kwargs from a manifest entry."""
    kw = {
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
        "requires_approval", "max_retries", "retry_delay",
        "retry_requires_approval", "priority", "thinking",
    ):
        val = entry.get(opt_field)
        if val is not None:
            kw[opt_field] = val
    return kw


def _strip_bound_param(schema):
    """Remove the first parameter (session) from a bound function's schema."""
    props = schema.get("properties", {})
    required = schema.get("required", [])
    if not props:
        return
    first_key = next(iter(props.keys()), None)
    if first_key:
        del props[first_key]
        if first_key in required:
            required.remove(first_key)


def _find_task_version(name, results):
    """Find the latest TaskDefinitionVersion by task name in results."""
    for td, tv in results:
        if td.name == name:
            return tv
    return None


def _find_agent_md_files(root_dir: Path):
    """Recursively find agent.md files, deduplicating nested paths."""
    paths = sorted(root_dir.glob("**/agent.md"),
                   key=lambda p: len(p.parts))
    result = []
    for p in paths:
        parent_str = p.parent.as_posix()
        if not any(
            parent_str.startswith(other.parent.as_posix())
            for other in result
        ):
            result.append(p)
    return result
