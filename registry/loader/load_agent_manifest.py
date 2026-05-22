import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import frontmatter
from django.core.exceptions import ValidationError

from registry.loader.load_scripts_manifest import load_scripts_manifest
from registry.loader.load_skill_manifest import load_skill_manifest
from registry.loader.utils import find_agent_md_files
from registry.shadow_git import get_or_init_shadow_repo
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.content import GenericContent
from server.models.providers.ai_model import AiModel
from server.models.settings import SettingsModel
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion


# ---------------------------------------------------------------------------
# Agent loader (agent.md)
# ---------------------------------------------------------------------------

def load_agent_manifest(
    agent_md_path: Path,
    parent_project: Any = None,
    parent_agent: Any = None,
    parent_skill: Any = None,
) -> Tuple[AgentModel, AgentVersionModel]:
    """Load an ``agent.md`` manifest into the database.

    Creates or updates the ``AgentModel`` and ``AgentVersionModel``, resolves
    child scripts, skills and subagents, builds a ``SettingsModel`` from the
    YAML frontmatter, and resolves task/subagent references.
    """
    print("load_agent_manifest", agent_md_path)
    manifest = frontmatter.load(agent_md_path)
    agent_dir = agent_md_path.parent
    commit = get_or_init_shadow_repo(agent_dir)

    def get_list(name: str) -> Optional[List[str]]:
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
    defined_tasks: List[Tuple[TaskDefinition, TaskDefinitionVersion]] = []
    scripts_dir = agent_dir / "scripts"
    if scripts_dir.is_dir():
        defined_tasks = load_scripts_manifest(
            scripts_dir,
            parent_project=parent_project,
            parent_agent=agent,
        )
    print("defined_tasks", defined_tasks)

    # Load child skills
    defined_skills: List[Tuple[Any, Any]] = []
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
    defined_subagents: List[Tuple[AgentModel, AgentVersionModel]] = []
    agents_dir = agent_dir / "agents"
    if agents_dir.is_dir():
        for sub_md in find_agent_md_files(agents_dir):
            subagent, sav = load_agent_manifest(
                sub_md,
                parent_project=parent_project,
                parent_agent=agent,
            )
            defined_subagents.append((subagent, sav))

    # Build SettingsModel
    aimodel = _get_ai_model(manifest.get("model"))
    extend_agent_names: List[str] = get_list("extends") or []

    # Parse subagents: field (accepts strings, or dicts with metadata)
    subagent_names: List[str] = []
    subagent_configs: Dict[str, Any] = {}
    raw_subagents = manifest.get("subagents")
    if raw_subagents is not None:
        if isinstance(raw_subagents, str):
            raw_subagents = [x.strip() for x in raw_subagents.split(",") if x.strip()]
        elif isinstance(raw_subagents, (list, tuple)):
            for entry in raw_subagents:
                if isinstance(entry, str):
                    name = entry.strip()
                    subagent_names.append(name)
                    subagent_configs[name] = {}
                elif isinstance(entry, dict):
                    name = entry.get("name", "").strip()
                    if name:
                        subagent_names.append(name)
                        subagent_configs[name] = {
                            k: v for k, v in entry.items() if k != "name"
                        }
                else:
                    raise Exception(f"unsupported type for{entry}")
        else:
            raise Exception(f"unsupported type for{raw_subagents}")
    print(
        "subagent_configs",
        agent_md_path,
        raw_subagents,
        subagent_configs,
        subagent_names,
    )

    settings_kwargs: Dict[str, Any] = {
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
        "subagentNames": subagent_names or [],
        "disallowedSubagentNames": get_list("disallowedSubagents"),
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
    extend_versions: List[AgentVersionModel] = []
    for ext_name in extend_agent_names:
        ext_agent = AgentModel.objects.get(name=ext_name)
        if ext_agent.latest_agent_version:
            extend_versions.append(ext_agent.latest_agent_version)
        else:
            raise Exception(f"no latest found for {ext_agent}")

    # Build hash from all dependencies
    dep_pks: List[str] = (
        [str(v.pk) for v in extend_versions]
        + [s for s in extend_agent_names if s]
        + [str(sv.pk) for _, sv in defined_skills]
        + [str(tv.pk) for _, tv in defined_tasks]
        + [str(sav.pk) for _, sav in defined_subagents]
    )
    print("EXTENDS", agent_md_path, extend_versions)
    hash_str = "_".join(sorted(set(dep_pks)))
    content_hash = hashlib.sha1(hash_str.encode()).hexdigest()

    current_vn = 1
    if agent.latest_agent_version:
        current_vn = agent.latest_agent_version.version_number
    print("current_vn", current_vn)

    agent_version, created = AgentVersionModel.objects.get_or_create(
        agent=agent,
        description=manifest.get("description", ""),
        extends_agent_names=extend_agent_names,
        commit=commit,
        agent_settings=settings,
        hash=content_hash,
        version_number__gte=current_vn,
    )
    if created:
        agent_version.extends_agent_versions.set(extend_versions)
        AgentVersionModel.objects.filter(pk=agent_version.pk).update(
            version_number=current_vn + 1
        )
        AgentModel.objects.filter(pk=agent.pk).update(
            latest_agent_version=agent_version
        )
        agent_version.defined_skill_versions.set([sv for _, sv in defined_skills])
        agent_version.defined_task_versions.set([tv for _, tv in defined_tasks])
        agent_version.defined_subagent_versions.set(
            [sav for _, sav in defined_subagents]
        )
        AgentVersionModel.objects.filter(pk=agent_version.pk).update(
            subagent_configs=subagent_configs
        )

    _resolve_agent_version_tasks(agent_version)
    _resolve_agent_version_subagents(agent_version)

    return agent, agent_version


def _resolve_agent_version_tasks(agent_version: AgentVersionModel) -> None:
    """Resolve tool / task / command names from the agent's ``SettingsModel``
    into ``TaskDefinitionVersion`` objects and set the M2M.

    Lookup precedence:
      1. own ``defined_task_versions``
      2. ``extends`` chain (parent agent versions)
      3. global (no parent_agent, no parent_project, no parent_skill)
    """
    settings = agent_version.agent_settings
    if not settings:
        return

    rt = agent_version.get_runtime()
    resolved: set = set()

    for names in [rt.allowedTaskNames, rt.allowedToolNames, rt.allowedCommandNames]:
        print("FOOOOO23", names)
        if not names:
            continue

        for name in names:
            print("slook", name)

            tdv = agent_version.defined_task_versions.filter(
                task_definition__name=name
            ).first()
            if tdv:
                resolved.add(tdv.pk)
                continue
            for ext in agent_version.extends_agent_versions.all():
                print("ETCENDS", ext, ext.defined_task_versions.all())
                tdv = ext.defined_task_versions.filter(
                    task_definition__name=name
                ).first()
                if tdv:
                    resolved.add(tdv.pk)
                    break
            else:
                print("SEARCH GLOBAL")
                tdv = (
                    TaskDefinition.objects.filter(
                        name=name,
                        parent_agent__isnull=True,
                        parent_project__isnull=True,
                        parent_skill__isnull=True,
                    )
                    .first()
                    .latest_task_version
                )
                print("found", tdv)
                resolved.add(tdv.pk)
    if not resolved:
        raise Exception(f"not found {name}")
    agent_version.task_versions.set(
        TaskDefinitionVersion.objects.filter(pk__in=resolved)
    )


def _resolve_agent_version_subagents(
    agent_version: AgentVersionModel,
) -> None:
    """Resolve subagent names from the agent's ``SettingsModel`` into
    ``AgentVersionModel`` objects and set ``subagent_versions`` M2M.

    Lookup precedence:
      1. own ``defined_subagent_versions``
      2. ``extends`` chain (parent agent versions)
      3. global (no parent_agent, no parent_project, no parent_skill)
    """
    settings = agent_version.agent_settings
    if not settings:
        raise Exception(f"{agent_version} has no settings")

    sa_names = settings.subagentNames
    if not sa_names:
        return

    resolved: set = set()
    for name in sa_names:
        sav = agent_version.defined_subagent_versions.filter(
            agent__name=name
        ).first()
        if sav:
            resolved.add(sav.pk)
            continue
        for ext in agent_version.extends_agent_versions.all():
            sav = ext.defined_subagent_versions.filter(agent__name=name).first()
            if sav:
                resolved.add(sav.pk)
                break
        else:
            sav = (
                AgentVersionModel.objects.filter(
                    agent__name=name,
                    agent__parent_agent__isnull=True,
                    agent__parent_project__isnull=True,
                )
                .order_by("-version_number")
                .first()
            )
            if not sav:
                raise Exception(f"No agent {name} found")
            resolved.add(sav.pk)
    print("SUBAGENTs", agent_version, resolved)
    if resolved:
        agent_version.subagent_versions.set(
            AgentVersionModel.objects.filter(pk__in=resolved)
        )


def _get_ai_model(model_name: Optional[str]) -> Optional[AiModel]:
    """Return the ``AiModel`` for *model_name*, or ``None``.

    Raises ``ValidationError`` when the model does not exist or is disabled.
    """
    if model_name is None:
        return None
    print("model_name", model_name)
    try:
        ai_model = AiModel.objects.get(name=model_name)
        if not ai_model.enabled:
            raise ValidationError(
                f"AI Model '{model_name}' exists but is not enabled."
            )
        return ai_model
    except AiModel.DoesNotExist as e:
        raise ValidationError(
            f"AI Model '{model_name}' does not exist in the database."
        ) from e
