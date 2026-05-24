from __future__ import annotations
from typing import TYPE_CHECKING, Any

from server.models.content import GenericContent
from server.models.skills.skill_version import SkillModelVersion
from server.models.tasks.task_definition_version import TaskDefinitionVersion

if TYPE_CHECKING:
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.agents.agent import AgentModel


class Agent:
    """
    Runtime wrapper around an AgentModel.

    Provides read access to agent-level settings resolved from the pinned (or
    latest) AgentVersion.  Commands, tasks, tools, skills and subagents are
    filtered through the allowed/disallowed lists stored on the version.
    """

    def __init__(
        self,
        agent_model: AgentModel,
        pinned_agent_version: AgentVersionModel | None = None,
    ) -> None:
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
    def max_history_messages(self) -> int:
        """Return the maximum number of history messages kept."""
        return self.get_version_model().resolve_setting("max_history_messages")

    @property
    def priority(self) -> int:
        """Return the scheduling priority."""
        return self.get_version_model().resolve_setting("priority")

    @property
    def scheduler_strategy(self) -> str:
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

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @property
    def commandNames(self) -> list[str]:
        """Return all configured command names."""
        return self.get_version_model().resolve_setting("commandNames") or []

    @property
    def disallowedCommandNames(self) -> list[str]:
        """Return disallowed command names."""
        return self.get_version_model().resolve_setting("disallowedCommandNames") or []

    @property
    def allowedCommandNames(self) -> list[str]:
        """Return command names minus those that are disallowed."""
        return list(set(self.commandNames) - set(self.disallowedCommandNames))

    @property
    def allowedCommands(self) -> list[TaskDefinitionVersion]:
        """Return :class:`TaskDefinitionVersion` instances for allowed commands."""
        return [t for t in [self.get_command(name) for name in self.allowedCommandNames] if t]

    def get_command(self, name: str) -> TaskDefinitionVersion | None:
        """Return the command *name* as a TaskDefinitionVersion, or *None*."""
        if name in self.allowedCommandNames:
            return self.get_version_model().commands().filter(task_definition__name=name).first()
        return None

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @property
    def taskNames(self) -> list[str]:
        """Return all configured task names."""
        return self.get_version_model().resolve_setting("taskNames") or []

    @property
    def disallowedTaskNames(self) -> list[str]:
        """Return disallowed task names."""
        return self.get_version_model().resolve_setting("disallowedTaskNames") or []

    @property
    def allowedTaskNames(self) -> list[str]:
        """Return task names minus those that are disallowed."""
        return list(set(self.taskNames) - set(self.disallowedTaskNames))

    @property
    def allowedTasks(self) -> list[TaskDefinitionVersion]:
        """Return :class:`TaskDefinitionVersion` instances for allowed tasks."""
        return [t for t in [self.get_task(name) for name in self.allowedTaskNames] if t]

    def get_task(self, name: str) -> TaskDefinitionVersion | None:
        """Return the task *name* as a TaskDefinitionVersion, or *None*."""
        if name in self.allowedTaskNames:
            return self.get_version_model().tasks().filter(task_definition__name=name).first()
        return None

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @property
    def toolNames(self) -> list[str]:
        """Return all configured tool names."""
        return self.get_version_model().resolve_setting("toolNames") or []

    @property
    def disallowedToolNames(self) -> list[str]:
        """Return disallowed tool names."""
        return self.get_version_model().resolve_setting("disallowedToolNames") or []

    @property
    def allowedToolNames(self) -> list[str]:
        """Return tool names minus those that are disallowed."""
        return list(set(self.toolNames) - set(self.disallowedToolNames))

    @property
    def allowedTools(self) -> list[TaskDefinitionVersion]:
        """Return :class:`TaskDefinitionVersion` instances for allowed tools."""
        return [t for t in [self.get_tool(name) for name in self.allowedToolNames] if t]

    def get_tool(self, name: str) -> TaskDefinitionVersion | None:
        """Return the tool *name* as a TaskDefinitionVersion, or *None*."""
        if name in self.allowedToolNames:
            return self.get_version_model().tools().filter(task_definition__name=name).first()
        return None

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
            return self.get_version_model().subagent_versions.filter(agent__name=name).first()
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
