from __future__ import annotations
from typing import TYPE_CHECKING, Any

from django.db.models import QuerySet

from server.models.content import GenericContent
from server.models.enums.task_enums import TaskType
from server.models.skills.skill_version import SkillModelVersion
from server.models.tasks.task_definition_version import TaskDefinitionVersion

if TYPE_CHECKING:
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.agents.agent import AgentModel


def is_name_disallowed(name: str, group_name: str, patterns: list[str]) -> bool:
    """Check if *name* (in *group_name*) matches any wildcard pattern.

    Supports the same syntax as the loader:

    - exact name: ``"tree"``
    - prefix wildcard: ``"tree*"`` → starts with ``"tree"``
    - suffix wildcard: ``"*tree"`` → ends with ``"tree"``
    - group wildcard: ``"filesystem-read.*"`` → all names in that group
    - group + prefix: ``"filesystem-read.tree*"``
    - group + suffix: ``"filesystem-read.*tree"``
    """
    for pattern in patterns:
        if "." in pattern:
            pat_group, pat_rest = pattern.split(".", 1)
            if pat_group != group_name:
                continue
            if pat_rest == "*":
                return True
            if pat_rest.endswith("*") and name.startswith(pat_rest[:-1]):
                return True
            if pat_rest.startswith("*") and name.endswith(pat_rest[1:]):
                return True
            if pat_rest == name:
                return True
        else:
            if pattern == name:
                return True
            if pattern.endswith("*") and name.startswith(pattern[:-1]):
                return True
            if pattern.startswith("*") and name.endswith(pattern[1:]):
                return True
    return False


class Agent:
    """
    Runtime wrapper around an AgentModel.

    Provides read access to agent-level settings resolved from the pinned (or
    latest) AgentVersion.  Commands, tasks, tools, skills and subagents are
    filtered through the allowed/disallowed lists stored on the version.
    """

    def __init__(self, agent_model: AgentModel, pinned_agent_version: AgentVersionModel | None = None) -> None:
        self.model: AgentModel = agent_model
        self._pinned_agent_version = pinned_agent_version

    # ------------------------------------------------------------------
    # Agent-level properties (from AgentModel)
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the agent's name."""
        return self.model.name

    # ------------------------------------------------------------------
    # Agent-version properties (from AgentVersionModel)
    # ------------------------------------------------------------------

    @property
    def description(self) -> str:
        """Return the description from the active version."""
        return self._get_agent_property("description")

    @property
    def visibility(self) -> str:
        """Return ``user`` | ``subagent`` | ``internal`` for the active version.

        Inherits through the extends chain (``planner`` inherits ``subagent``
        from ``researcher``); undeclared anywhere means ``user``.
        """
        return self._get_agent_property("visibility") or "user"

    @property
    def is_user_visible(self) -> bool:
        """Return whether the agent may be picked by a human user."""
        return self.visibility == "user"

    @property
    def version_number(self) -> int:
        """Return the version number of the active version."""
        return self.get_version_model().version_number

    # ------------------------------------------------------------------
    # Resolved settings
    # ------------------------------------------------------------------

    @property
    def aimodel(self) -> int | None:
        """Return the configured AI model ID, or *None*."""
        return self.get_version_model().resolve_setting("aimodel")

    @property
    def max_retries(self) -> int:
        """Return the maximum number of retries."""
        return self.get_version_model().resolve_setting("max_retries")

    @property
    def max_turns(self) -> int:
        """Return the maximum number of turns."""
        return self.get_version_model().resolve_setting("max_turns")

    @property
    def max_unattended_turns(self) -> int:
        """Return the maximum unattended turns allowed."""
        return self.get_version_model().resolve_setting("max_unattended_turns")

    @property
    def precision(self) -> int:
        """Return precision (temperature)  preset"""
        return self.get_version_model().resolve_setting("precision")

    @property
    def max_history_messages(self) -> int:
        """Return the maximum number of history messages kept."""
        return self.get_version_model().resolve_setting("max_history_messages")

    @property
    def auto_compact_max_tokens(self) -> int:
        """Return the hard token threshold for reactive auto-compaction (0 = disabled)."""
        return self.get_version_model().resolve_setting("auto_compact_max_tokens") or 0

    @property
    def auto_compact_min_tokens(self) -> int:
        """Return the context floor for idle-triggered compaction (0 = disabled)."""
        return self.get_version_model().resolve_setting("auto_compact_min_tokens") or 0

    @property
    def auto_compact_idle_seconds(self) -> int:
        """Return idle seconds triggering compaction of oversized sessions (0 = disabled)."""
        return self.get_version_model().resolve_setting("auto_compact_idle_seconds") or 0

    @property
    def priority(self) -> int:
        """Return the scheduling priority."""
        return self.get_version_model().resolve_setting("priority")

    @property
    def reasoning_effort(self) -> str | None:
        """Return the reasoning effort setting."""
        return self.get_version_model().resolve_setting("reasoning_effort")

    @property
    def scheduler_strategy(self) -> str | None:
        """Return the scheduler strategy name."""
        return self.get_version_model().resolve_setting("scheduler_strategy")

    @property
    def subagentResultDelivery(self) -> str:
        """Return the subagent result delivery mode (default: passive)."""
        return self.get_version_model().resolve_setting("subagentResultDelivery") or "passive"

    @property
    def tool_call_syntax(self) -> str:
        """Return the tool call syntax identifier."""
        return self.get_version_model().resolve_setting("tool_call_syntax")

    @property
    def task_prompt(self) -> str:
        """Return the task prompt, resolving GenericContent if stored as such."""
        tp = self.get_version_model().resolve_setting("task_prompt")
        if tp and isinstance(tp, GenericContent):
            return tp.get()
        return tp

    @property
    def system_prompt(self) -> str:
        """Return the system prompt, resolving GenericContent if stored as such."""
        sp = self.get_version_model().resolve_setting("system_prompt")
        if sp and isinstance(sp, GenericContent):
            return sp.get()
        return sp

    @property
    def inherit_system_prompt(self) -> bool:
        """Return whether this agent inherits parent system prompts."""
        return bool(self.get_version_model().resolve_setting("inherit_system_prompt"))

    @property
    def autoload(self) -> dict | None:
        """Return the AGENTS.md autoload config (or *None* when unset)."""
        value = self.get_version_model().resolve_setting("autoload")
        return dict(value) if isinstance(value, dict) else None

    @property
    def guidance_file_index_limit(self) -> int | None:
        """Return the guidance-file index cap override (or *None*)."""
        return self.get_version_model().resolve_setting("guidance_file_index_limit")

    @property
    def load_guidance_file_index(self) -> bool | None:
        """Return the guidance-file index toggle override (or *None*)."""
        return self.get_version_model().resolve_setting("load_guidance_file_index")

    @property
    def system_prompt_chain(self) -> list[str]:
        """Return all system prompts in inheritance order (if inheritSystemPrompt is enabled).

        Returns [parent_prompt, child_prompt] or just [child_prompt] depending
        on the inheritSystemPrompt setting.
        """
        if not self.inherit_system_prompt:
            # Only return this agent's own prompt
            sp = self.system_prompt
            return [sp] if sp else []
        # Return full chain from parent to child
        return self.get_version_model().collect_system_prompts()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @property
    def commandNames(self) -> list[str]:
        """Return all configured command names (raw, may include patterns)."""
        return self.get_version_model().resolve_setting("commandNames") or []

    @property
    def disallowedCommandNames(self) -> list[str]:
        """Return disallowed command names (raw, may include patterns)."""
        return self.get_version_model().resolve_setting("disallowedCommandNames") or []

    @property
    def allowedCommandNames(self) -> list[str]:
        """Return concrete command names, expanded from patterns via the resolved M2M."""
        disallowed = self.disallowedCommandNames
        return [
            tdv.task_definition.name
            for tdv in self.get_version_model().commands()
            if not is_name_disallowed(tdv.task_definition.name, tdv.task_definition.group_name, disallowed)
        ]

    @property
    def allowedCommands(self) -> list[TaskDefinitionVersion]:
        """Return :class:`TaskDefinitionVersion` instances for allowed commands, excluding disallowed."""
        disallowed = self.disallowedCommandNames
        return [
            tdv for tdv in self.get_version_model().commands()
            if not is_name_disallowed(tdv.task_definition.name, tdv.task_definition.group_name, disallowed)
        ]

    def get_command(self, name: str) -> TaskDefinitionVersion | None:
        """Return the command *name* as a TaskDefinitionVersion, or *None* (None if disallowed)."""
        if name in self.allowedCommandNames:
            return self.get_version_model().commands().filter(task_definition__name=name).first()
        return None

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @property
    def taskNames(self) -> list[str]:
        """Return all configured task names (raw, may include patterns)."""
        return self.get_version_model().resolve_setting("taskNames") or []

    @property
    def disallowedTaskNames(self) -> list[str]:
        """Return disallowed task names (raw, may include patterns)."""
        return self.get_version_model().resolve_setting("disallowedTaskNames") or []

    @property
    def allowedTaskNames(self) -> list[str]:
        """Return concrete task names, expanded from patterns via the resolved M2M."""
        disallowed = self.disallowedTaskNames
        return [
            tdv.task_definition.name
            for tdv in self.get_version_model().tasks()
            if not is_name_disallowed(tdv.task_definition.name, tdv.task_definition.group_name, disallowed)
        ]

    @property
    def allowedTasks(self) -> list[TaskDefinitionVersion]:
        """Return :class:`TaskDefinitionVersion` instances for allowed tasks, excluding disallowed."""
        disallowed = self.disallowedTaskNames
        return [
            tdv for tdv in self.get_version_model().tasks()
            if not is_name_disallowed(tdv.task_definition.name, tdv.task_definition.group_name, disallowed)
        ]

    def get_task(self, name: str) -> TaskDefinitionVersion | None:
        """Return the task *name* as a TaskDefinitionVersion, or *None* (None if disallowed)."""
        if name in self.allowedTaskNames:
            return self.get_version_model().tasks().filter(task_definition__name=name).first()
        return None

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @property
    def toolNames(self) -> list[str]:
        """Return all configured tool names (raw, may include patterns)."""
        return self.get_version_model().resolve_setting("toolNames") or []

    @property
    def disallowedToolNames(self) -> list[str]:
        """Return disallowed tool names (raw, may include patterns)."""
        return self.get_version_model().resolve_setting("disallowedToolNames") or []

    @property
    def allowedToolNames(self) -> list[str]:
        """Return concrete tool names, expanded from patterns via the resolved M2M."""
        disallowed = self.disallowedToolNames
        return [
            tdv.task_definition.name
            for tdv in self.get_version_model().tools()
            if not is_name_disallowed(tdv.task_definition.name, tdv.task_definition.group_name, disallowed)
        ]

    @property
    def allowedTools(self) -> list[TaskDefinitionVersion]:
        """Return :class:`TaskDefinitionVersion` instances for allowed tools, excluding disallowed."""
        disallowed = self.disallowedToolNames
        return [
            tdv for tdv in self.get_version_model().tools()
            if not is_name_disallowed(tdv.task_definition.name, tdv.task_definition.group_name, disallowed)
        ]

    def get_tool(self, name: str) -> TaskDefinitionVersion | None:
        """Return the tool *name* as a TaskDefinitionVersion, or *None* (None if disallowed)."""
        if name in self.allowedToolNames:
            return self.get_version_model().tools().filter(task_definition__name=name).first()
        return None

    # ------------------------------------------------------------------
    # All items (resolved, unfiltered — for UI display)
    # ------------------------------------------------------------------

    @property
    def all_tools(self) -> list[TaskDefinitionVersion]:
        """Return allowed tool TaskDefinitionVersions (respecting disallow list)."""
        return self.allowedTools

    @property
    def all_tasks(self) -> list[TaskDefinitionVersion]:
        """Return allowed task TaskDefinitionVersions (respecting disallow list)."""
        return self.allowedTasks

    @property
    def all_commands(self) -> list[TaskDefinitionVersion]:
        """Return allowed command TaskDefinitionVersions (respecting disallow list)."""
        return self.allowedCommands

    @property
    def all_skills(self) -> list[SkillModelVersion]:
        """Return allowed SkillModelVersions (respecting disallow list)."""
        return self.allowedSkills

    @property
    def all_subagents(self) -> list[AgentVersionModel]:
        """Return allowed subagent AgentVersionModels (respecting disallow list)."""
        return self.allowedSubagents

    # Defined-on-this-version items (unfiltered)

    @property
    def defined_tools(self) -> QuerySet:
        """Return tool TaskDefinitionVersions defined on this version."""
        return self.get_version_model().defined_task_versions.filter(
            task_type=TaskType.TOOL
        )

    @property
    def defined_tasks(self) -> QuerySet:
        """Return task TaskDefinitionVersions defined on this version."""
        return self.get_version_model().defined_task_versions.filter(
            task_type=TaskType.TASK
        )

    @property
    def defined_commands(self) -> QuerySet:
        """Return command TaskDefinitionVersions defined on this version."""
        return self.get_version_model().defined_task_versions.filter(
            task_type=TaskType.COMMAND
        )

    @property
    def defined_skills(self) -> QuerySet:
        """Return SkillModelVersions defined on this version."""
        return self.get_version_model().defined_skill_versions

    @property
    def defined_subagents(self) -> QuerySet:
        """Return subagent AgentVersionModels defined on this version."""
        return self.get_version_model().defined_subagent_versions

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    @property
    def skillNames(self) -> list[str]:
        """Return all configured skill names."""
        return self.get_version_model().resolve_setting("skillNames") or []

    @property
    def disallowedSkillNames(self) -> list[str]:
        """Return disallowed skill names."""
        return self.get_version_model().resolve_setting("disallowedSkillNames") or []

    @property
    def allowedSkillNames(self) -> list[str]:
        """Return skill names minus those that are disallowed."""
        return list(set(self.skillNames) - set(self.disallowedSkillNames))

    @property
    def allowedSkills(self) -> list[SkillModelVersion]:
        """Return :class:`SkillModelVersion` instances for allowed skills."""
        return [t for t in [self.get_skill(name) for name in self.allowedSkillNames] if t]

    def get_skill(self, name: str) -> SkillModelVersion | None:
        """Return the skill *name* as a SkillModelVersion, or *None*."""
        if name in self.allowedSkillNames:
            return self.get_version_model().skills().filter(skill__name=name).first()
        return None

    # ------------------------------------------------------------------
    # Subagents
    # ------------------------------------------------------------------

    @property
    def subagentNames(self) -> list[str]:
        """Return all configured subagent names."""
        return self.get_version_model().resolve_setting("subagentNames") or []

    @property
    def disallowedSubagentNames(self) -> list[str]:
        """Return disallowed subagent names."""
        return self.get_version_model().resolve_setting("disallowedSubagentNames") or []

    @property
    def allowedSubagentNames(self) -> list[str]:
        """Return subagent names minus those that are disallowed."""
        return list(set(self.subagentNames) - set(self.disallowedSubagentNames))

    @property
    def allowedSubagents(self) -> list[AgentVersionModel]:
        """Return allowed :class:`AgentVersionModel` instances for subagents."""
        return [s for s in [self.get_subagent(name) for name in self.allowedSubagentNames] if s]

    def get_subagent(self, name: str) -> AgentVersionModel | None:
        """Return the subagent *name* as an AgentVersionModel, or *None*."""
        if name in self.allowedSubagentNames:
            av = self.get_version_model().subagent_versions.filter(agent__name=name).first()
            if av is not None and av.get_runtime().visibility == "internal":
                # Internal agents (approval_decider, …) are framework-only:
                # instantiated by name in runtime code, never as subagents.
                return None
            return av
        return None

    def subagent_config(self, name: str) -> dict:
        """Return the subagent configuration dict for *name*."""
        return self.get_version_model().subagent_configs.get(name, {})

    @property
    def definedSubagentVersions(self) -> Any:
        """QuerySet of all subagent versions defined on this agent version."""
        return self.get_version_model().defined_subagent_versions.all()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def get_agent_setting(self, name: str) -> Any:
        return self.get_version_model().resolve_setting(name)

    def _get_agent_property(self, name: str) -> Any:
        """Resolve a free-form property from the active agent version."""
        return self.get_version_model().resolve_property(name)

    def get_version_model(self) -> AgentVersionModel:
        """Return the pinned version, or the agent's latest version."""
        if self._pinned_agent_version:
            return self._pinned_agent_version
        return self.model.latest_agent_version
