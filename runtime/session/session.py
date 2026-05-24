from __future__ import annotations
import ast
from typing import TYPE_CHECKING, Any, Dict, List

from runtime.agents.agent import Agent, is_name_disallowed
from runtime.tasks.bound_task import BoundTask
from server.models.content import GenericContent
from server.models.message import Message
from server.models.providers.ai_model import AiModel
from server.models.settings import ReasoningEffort, SettingsModel
from server.models.skills.skill_version import SkillModelVersion
from server.models.sessions.session import SessionModel
from server.models.tasks.task_definition_version import TaskDefinitionVersion

if TYPE_CHECKING:
    from server.models.sessions.session_version import SessionVersionModel
    from server.models.agents.agent_version import AgentVersionModel


class Session:
    """
    Runtime wrapper around a SessionModel.

    Reads are delegated to the pinned (or latest) SessionVersion, falling back
    to the pinned (or latest) AgentVersion for any setting not overridden in
    session_settings.  Mutating setters create a new SessionVersion each time
    (copy-on-write).
    """

    def __init__(
        self,
        session_model: SessionModel,
        pinned_session_version: SessionVersionModel | None = None,
    ) -> None:
        if not isinstance(session_model, SessionModel):
            raise Exception("foo23")
        self.model = session_model
        self._pinned_session_version = pinned_session_version

    # ------------------------------------------------------------------
    # Agent
    # ------------------------------------------------------------------

    @property
    def agent(self) -> Agent:
        """Return the runtime Agent associated with this session."""
        return self.get_version_model().agent.get_runtime()

    def set_agent(self, agent: Any) -> None:
        """Set the agent for this session (creates a new version)."""
        self._set_session_property("agent", agent)

    # ------------------------------------------------------------------
    # Session-level properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the session name."""
        return self.model.name

    @property
    def description(self) -> str:
        """Return the description from the active session version."""
        return self.get_version_model().description

    @property
    def workspace(self) -> Any:
        """Return the workspace from the active session version."""
        return self.get_version_model().workspace

    def set_workspace(self, value: Any) -> None:
        """Set the workspace for this session (creates a new version)."""
        self._set_session_property("workspace", value)

    @property
    def version_number(self) -> int:
        """Return the version number of the active session version."""
        return self.get_version_model().version_number

    # ------------------------------------------------------------------
    # Resolved session settings  (agent → session override)
    # ------------------------------------------------------------------

    @property
    def aimodel(self) -> AiModel | None:
        """Return the resolved AI model, or *None*."""
        return self._get_session_setting("aimodel")

    def set_aimodel(self, model: AiModel | None) -> None:
        """Override the AI model setting (creates a new version)."""
        self._set_session_setting("aimodel", model)

    @property
    def reasoning_effort(self) -> ReasoningEffort:
        """Return the resolved reasoning effort (defaults to NONE)."""
        return self._get_session_setting("reasoning_effort") or ReasoningEffort.NONE

    def set_reasoning_effort(self, value: ReasoningEffort) -> None:
        """Override the reasoning effort setting (creates a new version)."""
        self._set_session_setting("reasoning_effort", value)

    @property
    def max_retries(self) -> int:
        """Return the resolved max retries."""
        return self._get_session_setting("max_retries")

    @property
    def max_turns(self) -> int:
        """Return the resolved max turns."""
        return self._get_session_setting("max_turns")

    @property
    def current_turn_count(self) -> int:
        """Return the current turn count from the session model."""
        return self.model.turn_count

    def count_turn(self) -> None:
        """Increment the turn counter on the session model."""
        SessionModel.objects.filter(pk=self.model.pk).update(turn_count=self.model.turn_count + 1)

    def reset_turn_count(self) -> None:
        """Reset the turn counter to zero."""
        SessionModel.objects.filter(pk=self.model.pk).update(turn_count=0)

    @property
    def max_unattended_turns(self) -> int:
        """Return the resolved max unattended turns."""
        return self._get_session_setting("max_unattended_turns")

    @property
    def current_unattended_turn_count(self) -> int:
        """Return the current unattended turn count."""
        self.model.refresh_from_db()
        return self.model.unattended_turn_count

    def count_unattended_turn(self) -> None:
        """Increment the unattended turn counter."""
        SessionModel.objects.filter(pk=self.model.pk).update(unattended_turn_count=self.model.unattended_turn_count + 1)

    def reset_unattended_turn_count(self) -> None:
        """Reset the unattended turn counter to zero."""
        try:
            SessionModel.objects.filter(pk=self.model.pk).update(unattended_turn_count=0)
        except Exception as e:
            print("Failed to update", e)

    @property
    def max_history_messages(self) -> int:
        """Return the resolved max history messages."""
        return self._get_session_setting("max_history_messages")

    @property
    def priority(self) -> int:
        """Return the resolved scheduling priority."""
        return self._get_session_setting("priority")

    @property
    def task_prompt(self) -> str | None:
        """Return the resolved task prompt, resolving GenericContent if needed."""
        tp: GenericContent = self._get_session_setting("task_prompt")
        return tp.get() if tp and isinstance(tp, GenericContent) else tp

    @property
    def system_prompt(self) -> str | None:
        """Return the resolved system prompt, resolving GenericContent if needed."""
        sp: GenericContent = self._get_session_setting("system_prompt")
        return sp.get() if sp and isinstance(sp, GenericContent) else sp

    @property
    def scheduler_strategy(self) -> str | None:
        """Return the resolved scheduler strategy."""
        return self._get_session_setting("scheduler_strategy")

    @property
    def tool_call_syntax(self) -> str | None:
        """Return the resolved tool call syntax."""
        return self._get_session_setting("tool_call_syntax")

    # ------------------------------------------------------------------
    # Commands (resolved from agent, filtered by session overrides)
    # ------------------------------------------------------------------

    @property
    def commandNames(self) -> list[str]:
        """Return the resolved command names."""
        return self._get_session_setting("commandNames") or []

    @property
    def disallowedCommandNames(self) -> list[str]:
        """Return the resolved disallowed command names."""
        return self._get_session_setting("disallowedCommandNames") or []

    def _filter_allowed_names(self, tdvs: list[TaskDefinitionVersion], disallowed: list[str]) -> list[str]:
        """Return names from *tdvs* that don't match any disallowed pattern."""
        return [
            tdv.task_definition.name
            for tdv in tdvs
            if not is_name_disallowed(tdv.task_definition.name, tdv.task_definition.group_name, disallowed)
        ]

    @property
    def allowedCommandNames(self) -> list[str]:
        """Return concrete command names, expanded from patterns via the resolved M2M."""
        return self._filter_allowed_names(self.agent.allowedCommands, self.disallowedCommandNames)

    @property
    def allowedCommands(self) -> list[TaskDefinitionVersion]:
        """Return allowed command TaskDefinitionVersion instances (from agent)."""
        return list(self.agent.allowedCommands)

    def get_command(self, name: str) -> BoundTask | None:
        """Return a BoundTask for command *name*, or *None*."""
        tdv = self.agent.get_command(name)
        if tdv:
            return BoundTask(session=self, task_definition_version=tdv)
        return None

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @property
    def taskNames(self) -> list[str]:
        """Return the resolved task names."""
        return self._get_session_setting("taskNames") or []

    @property
    def disallowedTaskNames(self) -> list[str]:
        """Return the resolved disallowed task names."""
        return self._get_session_setting("disallowedTaskNames") or []

    @property
    def allowedTaskNames(self) -> list[str]:
        """Return concrete task names, expanded from patterns via the resolved M2M."""
        return self._filter_allowed_names(self.agent.allowedTasks, self.disallowedTaskNames)

    @property
    def allowedTasks(self) -> list[TaskDefinitionVersion]:
        """Return allowed task TaskDefinitionVersion instances (from agent)."""
        return list(self.agent.allowedTasks)

    def get_task(self, name: str) -> BoundTask | None:
        """Return a BoundTask for task *name*, or *None*."""
        tdv = self.agent.get_task(name)
        if tdv:
            return BoundTask(session=self, task_definition_version=tdv)
        return None

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @property
    def toolNames(self) -> list[str]:
        """Return the resolved tool names."""
        return self._get_session_setting("toolNames") or []

    @property
    def disallowedToolNames(self) -> list[str]:
        """Return the resolved disallowed tool names."""
        return self._get_session_setting("disallowedToolNames") or []

    @property
    def allowedToolNames(self) -> list[str]:
        """Return concrete tool names, expanded from patterns via the resolved M2M."""
        return self._filter_allowed_names(self.agent.allowedTools, self.disallowedToolNames)

    @property
    def allowedTools(self) -> list[TaskDefinitionVersion]:
        """Return allowed tool TaskDefinitionVersion instances (from agent)."""
        return list(self.agent.allowedTools)

    def get_tool(self, name: str) -> BoundTask | None:
        """Return a BoundTask for tool *name*, or *None*."""
        tdv = self.agent.get_tool(name)
        if tdv:
            return BoundTask(session=self, task_definition_version=tdv)
        return None

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    @property
    def skillNames(self) -> list[str]:
        """Return the resolved skill names."""
        return self._get_session_setting("skillNames") or []

    @property
    def disallowedSkillNames(self) -> list[str]:
        """Return the resolved disallowed skill names."""
        return self._get_session_setting("disallowedSkillNames") or []

    @property
    def allowedSkillNames(self) -> list[str]:
        """Return skill names minus those disallowed."""
        return list(set(self.skillNames) - set(self.disallowedSkillNames))

    def get_skill(self, name: str) -> SkillModelVersion | None:
        """Return the SkillModelVersion for *name*, or *None*."""
        if name in self.allowedSkillNames:
            return self.agent.get_skill(name)
        return None

    @property
    def subagentResultDelivery(self) -> str:
        """Return the resolved subagent result delivery mode (default: passive)."""
        return self._get_session_setting("subagentResultDelivery") or "passive"

    # ------------------------------------------------------------------
    # Session state
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """Return whether the session is active."""
        return self.model.is_active

    # ------------------------------------------------------------------
    # Subagents
    # ------------------------------------------------------------------

    @property
    def subagentNames(self) -> list[str]:
        """Return the resolved subagent names."""
        return self._get_session_setting("subagentNames") or []

    @property
    def disallowedSubagentNames(self) -> list[str]:
        """Return the resolved disallowed subagent names."""
        return self._get_session_setting("disallowedSubagentNames") or []

    @property
    def allowedSubagentNames(self) -> list[str]:
        """Return subagent names minus those disallowed."""
        return list(set(self.subagentNames) - set(self.disallowedSubagentNames))

    @property
    def allowedSubagents(self) -> list[AgentVersionModel]:
        """Return allowed subagent AgentVersionModel instances (from agent)."""
        return [s for s in [self.get_subagent(name) for name in self.allowedSubagentNames] if s]

    def get_subagent(self, name: str) -> AgentVersionModel | None:
        """Return the AgentVersionModel for subagent *name*, or *None*."""
        if name in self.allowedSubagentNames:
            return self.agent.get_subagent(name)
        return None

    def subagent_config(self, name: str) -> dict:
        """Return the subagent configuration dict for *name*."""
        return self.agent.subagent_config(name)

    # ------------------------------------------------------------------
    # Setting resolution  (agent → session override chain)
    # ------------------------------------------------------------------

    def _get_session_setting(self, name: str) -> Any:
        """
        Resolve a setting by checking the session's override first, then
        falling back to the agent version's configured value.

        List-typed settings support a wildcard ``"+"`` that marks the
        insertion point where the agent-level list is spliced in.
        """
        print("_get_session_setting", name)
        session_settings = self.get_version_model().session_settings
        print(session_settings)
        if not session_settings:  # we overwrite nothing, use agents profile
            print("we dont")
            return self.agent.get_agent_setting(name)

        # we might overwrite agent profile values
        session_settings_value = getattr(session_settings, name)
        if session_settings_value is None:  # we dont..
            print("we dont 2")
            return self.agent.get_agent_setting(name)

        if isinstance(session_settings_value, (str, int, bool, GenericContent)):
            return session_settings_value

        if isinstance(session_settings_value, (list,)):
            if "+" not in session_settings_value:  # overwrite parent list
                print("r1")
                return session_settings_value
            extend_at_index = session_settings_value.index("+")
            session_settings_value[extend_at_index:extend_at_index + 1] = self.agent.get_agent_setting(name)
        else:
            raise Exception(
                f"_get_session_setting does not yet support type of '{name}': "
                f"{type(session_settings_value)}"
            )
        print("r2, ", session_settings_value)
        return session_settings_value

    def _set_session_setting(self, name: str, value: Any) -> None:
        """
        Persist a setting override.  Creates a new SettingsModel row and a new
        SessionVersion row (copy-on-write).
        """
        session_version_model = self.get_version_model()
        if not session_version_model.session_settings:
            new_session_setting = SettingsModel()
        else:
            new_session_setting = session_version_model.session_settings

        if getattr(new_session_setting, name) == value:
            return
        new_session_setting.pk = None
        new_session_setting.created_at = None
        new_session_setting.__setattr__(name, value)
        new_session_setting.save()
        session_version_model.pk = None
        session_version_model.created_at = None
        session_version_model.version_number += 1
        session_version_model.save()
        self.model.latest_session_version = session_version_model
        self.model.save()

    def _set_session_property(self, name: str, value: Any) -> None:
        """
        Persist a property override on the session version.
        Creates a new SessionVersion row (copy-on-write).
        """
        session_version_model = self.get_version_model()
        if getattr(session_version_model, name) == value:
            return
        session_version_model.pk = None
        session_version_model.created_at = None
        session_version_model.version_number += 1
        session_version_model.__setattr__(name, value)
        session_version_model.save()
        self.model.latest_session_version = session_version_model
        self.model.save()

    def get_version_model(self) -> SessionVersionModel:
        """Return the pinned session version, or the session's latest version."""
        if self._pinned_session_version:
            return self._pinned_session_version
        print("NODEL", self.model, self.model.latest_session_version)
        return self.model.latest_session_version

    def is_newest_version(self):
        if self._pinned_session_version:
            return self._pinned_session_version == self.model.latest_session_version
        return True
     

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    def add_user_message(self, parts: List[Dict] | None = None) -> Any:
        """
        Ingest a user message (list of parts from parse_llm_response).

        If the first part's content starts with ``/`` it is treated as a slash
        command; otherwise it is dispatched as a regular user message.

        Parameters
        ----------
        parts : list[dict] | None
            Each part is a dict with at minimum:
            - ``type`` : ``"message"`` | ``"reasoning"`` | ``"toolcall"``
            - ``content_type`` : ``"text"`` | ``"image"`` | ``"template"`` | ``"json"``
            - ``content`` : str | dict
        """
        if not parts:
            raise Exception("No message or message parts provided")

        if parts[0] and parts[0].get("content", [None, ])[0] == "/":  # might be command
            cmd = parts[0].get("content", [None, ]).split(None, 1)[0][1:].strip()  # Get command without '/'
            print("CMD", cmd)
            bound_cmd = self.get_command(cmd)
            if bound_cmd:
                full_cmd_str = "".join([part["content"] for part in parts]).strip() if parts else ""
                cmd_payload = full_cmd_str[1 + len(cmd):].strip()
                # Safely parse arguments and keyword arguments
                _payload_ast_tree = ast.parse(f"f({cmd_payload})")
                call = _payload_ast_tree.body[0].value if _payload_ast_tree.body else None
                kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords} if call else {}

                return self.get_task("ingest_slash_command").delay(name=cmd, **kwargs)

        return self.get_task("ingest_user_message").delay(parts=parts)

    def get_messages(self) -> Any:
        """Return all messages for this session."""
        return Message.objects.filter(session_version__session=self.model)
