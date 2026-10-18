import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import frontmatter
from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet

from registry.install_repo import InstallRepo
from registry.loader.load_scripts_manifest import load_scripts_manifest
from registry.loader.load_skill_manifest import load_skill_manifest
from registry.loader.utils import find_agent_md_files
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel, AgentVisibility
from server.models.content import GenericContent
from server.models.providers.ai_model import AiModel
from server.models.settings import ResponseTemperature, SettingsModel
from server.models.skills.skill_version import SkillModelVersion
from server.models.tasks.scripts_generation import ScriptsGeneration
from server.models.tasks.task_definition import TaskDefinition
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from runtime.workspace_access import validate_agent_access
from runtime.guidance_files import validate_autoload_block


# ---------------------------------------------------------------------------
# Agent loader (agent.md)
# ---------------------------------------------------------------------------

def _validate_non_negative_int(value: Any, key: str, agent_name: str) -> Any:
    """Validate an optional non-negative-int manifest key; *None* passes through."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f"[agent.md {agent_name!r}] {key} must be an integer >= 0, got {value!r}"
        )
    return value


#: Session-hook lifecycle events (see ``docs/session-hooks.md`` §5).
HOOK_EVENTS = ("stop", "pre_compact", "post_compact", "session_end")

#: Code defaults for hook entries when the keys are omitted (explicit ``0``
#: means unbounded context / no deadline).
DEFAULT_HOOK_MAX_TOKENS = 40000
DEFAULT_HOOK_TIMEOUT_SECONDS = 300

#: Execution modes for intercept hooks: ``inline`` blocks the intercepted
#: call (transform contract), ``detached`` fires and forgets.
INTERCEPT_MODES = ("inline", "detached")

#: Failure policies for intercept hooks: ``fail_closed`` blocks/cancels the
#: parent on hook failure, ``fail_open`` lets the parent proceed.
INTERCEPT_ON_ERRORS = ("fail_open", "fail_closed")

#: Allowed ``match.type`` values (``TaskType`` names).
MATCH_TYPES = ("TOOL", "TASK", "COMMAND", "WEBAPI", "WEBVIEW")

_HOOK_KEYS = frozenset(
    {"name", "on", "matcher", "agent", "task", "ingest", "max_tokens",
     "timeout_seconds", "blocking",
     "match", "before", "after", "mode", "on_error"}
)

_MATCH_KEYS = frozenset({"name", "type", "session"})


def _normalize_match(raw: Any, where: str) -> dict:
    """Normalize an intercept ``match:`` filter into a JSON-safe dict.

    Accepts a shorthand string (a definition-name glob) or a mapping with
    optional ``name``/``type``/``session`` keys. Missing dimensions match
    everything. Lists are joined with ``" | "`` alternation.
    """
    if raw is None:
        return {}
    if isinstance(raw, str):
        if not raw.strip():
            raise ValueError(f"{where} match must be a non-empty string, got {raw!r}")
        return {"name": raw.strip()}
    if not isinstance(raw, dict):
        raise ValueError(f"{where} match must be a string or mapping, got {raw!r}")
    unknown = set(raw) - _MATCH_KEYS
    if unknown:
        raise ValueError(f"{where} match has unknown keys: {sorted(unknown)}")
    normalized: dict[str, str] = {}
    for key in ("name", "session"):
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            value = " | ".join(str(v) for v in value)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{where} match.{key} must be a non-empty string, got {raw.get(key)!r}")
        normalized[key] = value.strip()
    type_value = raw.get("type")
    if type_value is not None:
        if not isinstance(type_value, str) or type_value.strip().upper() not in MATCH_TYPES:
            raise ValueError(
                f"{where} match.type must be one of {list(MATCH_TYPES)}, got {type_value!r}"
            )
        normalized["type"] = type_value.strip().upper()
    return normalized


def _validate_hooks(raw: Any, agent_name: str) -> list[dict]:
    """Validate an agent.md ``hooks:`` block into normalized entry dicts.

    Two entry flavors (mutually exclusive):

    - Lifecycle entries name an event (``on``) and the task to run detached
      in a fork (``task``, optionally on another ``agent``), with an optional
      parent-side ``ingest`` task and budgets.
    - Intercept entries declare ``before`` (pre, receives original kwargs)
      or ``after`` (post, receives original result) naming a task of the
      *same* agent, an optional ``match:`` filter (definition name glob,
      ``type``, session-name glob), a ``mode`` (``inline`` = blocking
      transform, ``detached`` = fire-and-forget) and an ``on_error``
      policy. No ``on:`` key — ``before`` *is* pre, ``after`` *is* post.
      (There is deliberately no agent dimension: entries resolve from the
      session agent and execute in the intercepted call's own session, so
      an agent filter could only ever match yourself.)

    Returns a JSON-safe list (own entries only — extends-chain merging
    happens at runtime in ``Agent.hooks``).
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(
            f"[agent.md {agent_name!r}] hooks must be a list, got {raw!r}"
        )
    entries: list[dict] = []
    for i, entry in enumerate(raw):
        where = f"[agent.md {agent_name!r}] hooks[{i}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{where} must be a mapping, got {entry!r}")
        # YAML 1.1 parses an unquoted ``on:`` key as boolean True —
        # normalize it back (same reason cron ``on:`` keys are quoted).
        if True in entry and "on" not in entry:
            entry = {("on" if k is True else k): v for k, v in entry.items()}
        unknown = set(entry) - _HOOK_KEYS
        if unknown:
            raise ValueError(f"{where} has unknown keys: {sorted(unknown)}")
        if entry.get("blocking"):
            raise ValueError(
                f"{where} blocking hooks are the deferred sync tier "
                f"(docs/session-hooks.md §11) — omit blocking for now"
            )
        has_before = entry.get("before") is not None
        has_after = entry.get("after") is not None
        has_on = entry.get("on") is not None
        if has_before and has_after:
            raise ValueError(f"{where} must declare exactly one of before/after, got both")
        if has_on and (has_before or has_after):
            raise ValueError(
                f"{where} lifecycle entries (on:) and intercept entries "
                f"(before:/after:) are mutually exclusive"
            )
        if has_before or has_after:
            entries.append(_validate_intercept_hook(entry, where, agent_name, i))
            continue
        if not has_on:
            raise ValueError(
                f"{where} must declare on: (lifecycle) or before:/after: (intercept)"
            )
        entries.append(_validate_lifecycle_hook(entry, where, agent_name, i))
    return entries


def _validate_lifecycle_hook(entry: dict, where: str, agent_name: str, i: int) -> dict:
    """Validate one lifecycle hook entry (``on:`` + ``task:``)."""
    on = entry.get("on")
    if on not in HOOK_EVENTS:
        raise ValueError(
            f"{where} on must be one of {list(HOOK_EVENTS)}, got {on!r}"
        )
    for key in ("match", "before", "after", "mode", "on_error"):
        if entry.get(key) is not None:
            raise ValueError(f"{where} {key} is only valid on intercept (before:/after:) entries")
    task = entry.get("task")
    if not task or not isinstance(task, str):
        raise ValueError(f"{where} task must be a non-empty string, got {task!r}")
    matcher = entry.get("matcher")
    if matcher is not None and not isinstance(matcher, str):
        raise ValueError(f"{where} matcher must be a string, got {matcher!r}")
    hook_agent = entry.get("agent")
    if hook_agent is not None and (
        not isinstance(hook_agent, str) or not hook_agent.strip()
    ):
        raise ValueError(
            f"{where} agent must be a non-empty string, got {hook_agent!r}"
        )
    ingest = entry.get("ingest")
    if ingest is not None and (not isinstance(ingest, str) or not ingest.strip()):
        raise ValueError(
            f"{where} ingest must be a non-empty string, got {ingest!r}"
        )
    max_tokens = _validate_non_negative_int(
        entry.get("max_tokens"), f"hooks[{i}].max_tokens", agent_name
    )
    timeout_seconds = _validate_non_negative_int(
        entry.get("timeout_seconds"), f"hooks[{i}].timeout_seconds", agent_name
    )
    name = entry.get("name") or task
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{where} name must be a non-empty string, got {name!r}")
    normalized = {
        "name": name.strip(),
        "on": on,
        "task": task.strip(),
        "max_tokens": (
            DEFAULT_HOOK_MAX_TOKENS if max_tokens is None else max_tokens
        ),
        "timeout_seconds": (
            DEFAULT_HOOK_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
        ),
    }
    if matcher is not None:
        normalized["matcher"] = matcher
    if hook_agent is not None:
        normalized["agent"] = hook_agent.strip()
    if ingest is not None:
        normalized["ingest"] = ingest.strip()
    return normalized


def _validate_intercept_hook(entry: dict, where: str, agent_name: str, i: int) -> dict:
    """Validate one intercept hook entry (``before:`` or ``after:``)."""
    for key in ("on", "matcher", "agent", "task", "ingest", "max_tokens"):
        if entry.get(key) is not None:
            raise ValueError(
                f"{where} {key} is only valid on lifecycle (on:) entries, "
                f"not intercept (before:/after:) entries"
            )
    hook_task = entry.get("before") if entry.get("before") is not None else entry.get("after")
    if not isinstance(hook_task, str) or not hook_task.strip():
        raise ValueError(
            f"{where} before/after must name a task of the same agent, got {hook_task!r}"
        )
    if entry.get("timeout_seconds") is not None:
        raise ValueError(
            f"{where} timeout_seconds is not supported on intercept "
            f"(before:/after:) entries"
        )
    position = "before" if entry.get("before") is not None else "after"
    match = _normalize_match(entry.get("match"), where)
    mode = entry.get("mode")
    if mode is None:
        mode = "inline" if position == "before" else "detached"
    if mode not in INTERCEPT_MODES:
        raise ValueError(
            f"{where} mode must be one of {list(INTERCEPT_MODES)}, got {mode!r}"
        )
    on_error = entry.get("on_error")
    if on_error is None:
        on_error = "fail_closed" if mode == "inline" else "fail_open"
    if on_error not in INTERCEPT_ON_ERRORS:
        raise ValueError(
            f"{where} on_error must be one of {list(INTERCEPT_ON_ERRORS)}, got {on_error!r}"
        )
    if position == "before" and mode == "inline" and on_error != "fail_closed":
        raise ValueError(
            f"{where} inline before hooks cannot fail open (a failed input "
            f"transform has no sound fallback) — use on_error: fail_closed "
            f"or mode: detached"
        )
    name = entry.get("name") or hook_task
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{where} name must be a non-empty string, got {name!r}")
    normalized: dict[str, Any] = {
        "name": name.strip(),
        position: hook_task.strip(),
        "match": match,
        "mode": mode,
        "on_error": on_error,
    }
    return normalized


def load_agent_manifest(
    agent_md_path: Path,
    install_repo: InstallRepo,
    parent_project: Any = None,
    parent_agent: Any = None,
    parent_skill: Any = None,
    details: list | None = None,
) -> Tuple[AgentModel, AgentVersionModel]:
    """Load an ``agent.md`` manifest into the database.

    Creates or updates the ``AgentModel`` and ``AgentVersionModel``, resolves
    child scripts, skills and subagents, builds a ``SettingsModel`` from the
    YAML frontmatter, and resolves task/subagent references.

    Version identifiers are deterministic git tree SHAs from *install_repo*.
    """
    manifest = frontmatter.load(agent_md_path)
    agent_dir = agent_md_path.parent
    commit = install_repo.tree_sha(agent_dir)

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
        # AgentModel.save() forbids updates on existing rows (immutability
        # guard), so renames must go through a queryset update — a pure
        # name change that keeps the row (and all FK references from
        # sessions/versions) intact.
        AgentModel.objects.filter(pk=agent.pk).update(name=name)
        agent.name = name
    else:
        agent, _ = AgentModel.objects.get_or_create(
            name=name,
            parent_project=parent_project,
            parent_agent=parent_agent,
            parent_skill=parent_skill,
        )

    # Record where this agent's manifest lives. AgentModel.save() forbids
    # updates on existing rows, so drift goes through a queryset update.
    manifest_dir = agent_dir.as_posix()
    if (agent.manifest_dir or "") != manifest_dir:
        AgentModel.objects.filter(pk=agent.pk).update(manifest_dir=manifest_dir)
        agent.manifest_dir = manifest_dir

    # Load child scripts
    defined_tasks: List[Tuple[TaskDefinition, TaskDefinitionVersion]] = []
    scripts_dir = agent_dir / "scripts"
    if scripts_dir.is_dir():
        defined_tasks = load_scripts_manifest(
            scripts_dir,
            parent_project=parent_project,
            parent_agent=agent,
            install_repo=install_repo,
        )

    # Load child skills
    defined_skills: List[Tuple[Any, Any]] = []
    skills_dir = agent_dir / "skills"
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("**/skill.md")):
            skill, sv = load_skill_manifest(
                skill_md,
                parent_project=parent_project,
                parent_agent=agent,
                install_repo=install_repo,
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
                install_repo=install_repo,
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

    settings_kwargs: Dict[str, Any] = {
        "aimodel": aimodel,
        "max_retries": manifest.get("maxRetries"),
        "max_turns": manifest.get("maxTurns"),
        "max_unattended_turns": manifest.get("maxUnattendedTurns"),
        "max_history_messages": manifest.get("maxHistoryMessages"),
        "scheduler_strategy": manifest.get("schedulerStrategy"),
        "tool_call_syntax": manifest.get("toolCallSyntax"),
        "reasoning_effort": manifest.get("reasoningEffort"),
        "precision": manifest.get("precision"),
        "subagentResultDelivery": manifest.get("subagentResultDelivery"),
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
        "auto_compact_max_tokens": manifest.get(
            "autoCompactMaxTokens", manifest.get("autoCompactLimit")
        ),
        "auto_compact_min_tokens": _validate_non_negative_int(
            manifest.get("autoCompactMinTokens"), "autoCompactMinTokens", agent.name
        ),
        "auto_compact_idle_seconds": _validate_non_negative_int(
            manifest.get("autoCompactIdleSeconds"), "autoCompactIdleSeconds", agent.name
        ),
        "auto_compact_keep_percent": manifest.get("autoCompactKeepPercent"),
        "priority": manifest.get("priority"),
        "thinking": manifest.get("thinking"),
        "inherit_system_prompt": manifest.get("inheritSystemPrompt"),
        "system_prompt": GenericContent.from_text(
            (manifest.content or "").strip()
        ),
        "commit": commit,
    }

    settings_kwargs = {k: v for k, v in settings_kwargs.items() if v is not None}

    # Filesystem access policy (agent.md ``access:`` block)
    access_block = manifest.get("access")
    if access_block is not None:
        validate_agent_access(access_block, source=f"agent.md {agent.name!r}")
        settings_kwargs["access"] = access_block

    # Agent visibility (``visibility: user | subagent | internal | mixin``) — who the
    # agent is meant for. Undeclared stays NULL (inherit through extends,
    # else user) so existing rows keep matching and no version bumps.
    visibility = manifest.get("visibility")
    if visibility is not None:
        valid = {c.value for c in AgentVisibility}
        if visibility not in valid:
            raise ValueError(
                f"[agent.md {agent.name!r}] visibility must be one of "
                f"{sorted(valid)}, got {visibility!r}"
            )
    # AGENTS.md autoload (agent.md ``autoload:`` block + ``agentsMdIndexLimit``)
    autoload_block = manifest.get("autoload")
    if autoload_block is not None:
        settings_kwargs["autoload"] = validate_autoload_block(
            autoload_block, source=f"agent.md {agent.name!r}"
        )
    index_limit = manifest.get("guidanceFileIndexLimit")
    if index_limit is not None:
        if (
            isinstance(index_limit, bool)
            or not isinstance(index_limit, int)
            or index_limit < 0
        ):
            raise ValueError(
                f"[agent.md {agent.name!r}] guidanceFileIndexLimit must be an "
                f"integer >= 0, got {index_limit!r}"
            )
        settings_kwargs["guidance_file_index_limit"] = index_limit

    # Session hooks (agent.md ``hooks:`` block — lifecycle event → matcher →
    # detached fork handler; see docs/session-hooks.md). Own entries only;
    # the extends-chain merge happens at runtime (``Agent.hooks``).
    hook_entries = _validate_hooks(manifest.get("hooks"), agent.name)

    # Nested guidance-file index (standalone ``loadGuidanceFileIndex`` key —
    # independent of ``autoload:``, which only controls pinned contents).
    load_index = manifest.get("loadGuidanceFileIndex")
    if load_index is not None:
        if not isinstance(load_index, bool):
            raise ValueError(
                f"[agent.md {agent.name!r}] loadGuidanceFileIndex must be a "
                f"boolean, got {load_index!r}"
            )
        settings_kwargs["load_guidance_file_index"] = load_index

    if settings_kwargs.get("precision",None):
        key = settings_kwargs.get("precision","").upper()
        settings_kwargs["precision"] = ResponseTemperature[key].value

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
    hash_str = "_".join(sorted(set(dep_pks)))
    content_hash = hashlib.sha1(hash_str.encode()).hexdigest()

    current_vn = 1
    if agent.latest_agent_version:
        current_vn = agent.latest_agent_version.version_number

    agent_version, created = AgentVersionModel.objects.get_or_create(
        agent=agent,
        description=manifest.get("description", ""),
        visibility=visibility,
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
        AgentVersionModel.objects.filter(pk=agent_version.pk).update(
            hooks=hook_entries
        )
    if details is not None:
        action = "created" if created else "up to date"
        details.append({"name": agent.name, "type": "agent", "action": action})

    _resolve_agent_version_tasks(agent_version)
    _resolve_agent_version_skills(agent_version)
    _resolve_agent_version_subagents(agent_version)

    return agent, agent_version


def _resolve_agent_version_tasks(
    agent_version: AgentVersionModel,
) -> None:
    """Resolve tool / task / command names from the agent's ``SettingsModel``
    into ``TaskDefinitionVersion`` objects and set the M2M.

    Lookup precedence:
      1. own ``defined_task_versions``
      2. ``extends`` chain (parent agent versions)
      3. global (no parent_agent, no parent_project, no parent_skill)

    Global task resolution is scoped to the latest ``ScriptsGeneration``,
    which prevents orphaned tool definitions (e.g. after a rename) from
    appearing as available tools.
    """
    settings = agent_version.agent_settings
    if not settings:
        return

    resolved: set = set()

    def _add_matches(qs: QuerySet, target: set) -> bool:
        found = False
        for tdv in qs:
            target.add(tdv.pk)
            found = True
        return found

    def _resolve_pattern(pattern: str) -> None:
        """Resolve a single name or wildcard pattern into TDV pks."""
        if pattern == "+":
            return
        group = ""
        if "." in pattern:
            group, raw_name = [x.strip() for x in pattern.strip().split(".", 1)]
        else:
            raw_name = pattern

        is_wildcard = raw_name in ("*",) or raw_name.startswith("*") or raw_name.endswith("*")

        fargs: dict[str, Any] = {}
        if raw_name != "*":
            if raw_name.startswith("*"):
                fargs["task_definition__name__startswith"] = raw_name[1:]
            elif raw_name.endswith("*"):
                fargs["task_definition__name__endswith"] = raw_name[:-1]
            else:
                fargs["task_definition__name"] = raw_name
        if group:
            fargs["task_definition__group_name"] = group

        # 1. Own defined_task_versions
        if _add_matches(agent_version.defined_task_versions.filter(**fargs), resolved):
            return

        # 2. Extends chain (recursive) — wildcards collect from all,
        #    exact first-match wins
        found_in_extends = False
        visited: set = set()

        def _walk(av: Any) -> None:
            nonlocal found_in_extends
            if av.pk in visited:
                return
            visited.add(av.pk)
            for ext in av.extends_agent_versions.all():
                if _add_matches(ext.defined_task_versions.filter(**fargs), resolved):
                    found_in_extends = True
                    if not is_wildcard:
                        return
                _walk(ext)

        _walk(agent_version)
        if found_in_extends:
            return

        # 3. Global fallback — only tasks from the latest ScriptsGeneration
        gfargs = {
            k.replace("task_definition__", ""): v
            for k, v in fargs.items()
        }
        gfargs["parent_agent__isnull"] = True
        gfargs["parent_project__isnull"] = True
        gfargs["parent_skill__isnull"] = True

        latest_gen = ScriptsGeneration.objects.order_by("-created_at").first()
        if latest_gen:
            gfargs["parent_generation"] = latest_gen

        global_tds = list(TaskDefinition.objects.filter(**gfargs))
        if not global_tds:
            avail_groups = sorted(
                TaskDefinition.objects.filter(
                    parent_agent__isnull=True,
                    parent_project__isnull=True,
                    parent_skill__isnull=True,
                ).values_list("group_name", flat=True).distinct()
            )
            hint = (
                f"No Task Definition found for '{raw_name}' group='{group}'. "
                f"Available global task groups: {avail_groups or '(none)'}. "
                f"Check that the referenced scripts.md loaded successfully — "
                f"a 'Scripts:' error earlier in reload output (e.g. a chain "
                f"step that couldn't be resolved) will abort all script "
                f"loading and cause this."
            )
            raise Exception(hint)
        for td in global_tds:
            resolved.add(td.latest_task_version.pk)

    # Read raw patterns via resolve_setting to walk the extends chain,
    # NOT through the runtime Agent (the M2M hasn't been populated yet).
    raw_namesets = [
        ("toolNames", agent_version.resolve_setting("toolNames") or []),
        ("taskNames", agent_version.resolve_setting("taskNames") or []),
        ("commandNames", agent_version.resolve_setting("commandNames") or []),
    ]

    cnt = 0
    for setting_key, names in raw_namesets:
        for name in names:
            cnt+=1
            try:
                _resolve_pattern(name)
            except Exception as e:
                raise Exception(
                    f"{e} (resolving agent '{agent_version.agent.name}' "
                    f"{setting_key} pattern '{name}')"
                ) from e

    if not resolved and cnt > 0:
        raise Exception(f"No task definitions resolved for pattern {raw_namesets}")
    agent_version.task_versions.set(
        TaskDefinitionVersion.objects.filter(pk__in=resolved)
    )


def _resolve_agent_version_skills(
    agent_version: AgentVersionModel,
) -> None:
    """Resolve skill names from the agent's ``SettingsModel`` into
    ``SkillModelVersion`` objects and set ``skill_versions`` M2M.

    Lookup precedence:
      1. own ``defined_skill_versions``
      2. ``extends`` chain (parent agent versions)
      3. any ``SkillModelVersion`` matching the name in the DB
    """
    settings = agent_version.agent_settings
    if not settings:
        return

    skill_names = agent_version.resolve_setting("skillNames")
    if not skill_names:
        return

    resolved: set = set()
    for name in skill_names:
        sv = agent_version.defined_skill_versions.filter(
            skill__name=name
        ).first()
        if sv:
            resolved.add(sv.pk)
            continue
        for ext in agent_version.extends_agent_versions.all():
            sv = ext.defined_skill_versions.filter(skill__name=name).first()
            if sv:
                resolved.add(sv.pk)
                break
        else:
            sv = (
                SkillModelVersion.objects.filter(skill__name=name)
                .order_by("-version_number")
                .first()
            )
            if not sv:
                raise Exception(f"No skill '{name}' found for agent '{agent_version.agent.name}'")
            resolved.add(sv.pk)

    if resolved:
        agent_version.skill_versions.set(
            SkillModelVersion.objects.filter(pk__in=resolved)
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
    if resolved:
        agent_version.subagent_versions.set(
            AgentVersionModel.objects.filter(pk__in=resolved)
        )


def _get_ai_model(model_name: Optional[str]) -> Optional[AiModel]:
    """Return the ``AiModel`` for *model_name*, or ``None``.

    ``None``, empty, or the sentinel ``"default"`` mean "no specific model" —
    the resolved session model then falls back to the user's configured
    default model.  Otherwise raises ``ValidationError`` when the model does
    not exist or is disabled.
    """
    if not model_name or model_name == "default":
        return None
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
