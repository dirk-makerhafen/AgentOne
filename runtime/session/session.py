from __future__ import annotations
import ast
import json
from typing import TYPE_CHECKING, Any, Dict, List

from django.db import transaction
from django.db.models import Sum

from runtime.agents.agent import Agent, is_name_disallowed
from runtime.tasks.bound_task import BoundTask
from server.models.content import GenericContent
from server.models.message import Message
from server.models.providers.ai_model import AiModel
from server.models.queries.query import Query, QueryStatus
from server.models.queries.response import Response, ResponseStatus
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
    def session_type(self) -> str:
        """Return the session type (SessionType value)."""
        return self.model.session_type

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
        """Return the resolved AI model, or *None*.

        When neither the session nor the agent pin a specific model (agent.md
        ``model:`` empty or ``default``), falls back to the user's configured
        Default Model.
        """
        model = self._get_session_setting("aimodel")
        if model is not None:
            return model
        return self._default_aimodel()

    def unresolved_aimodel(self) -> AiModel | None:
        """The AI model pinned by the session or its agent, or *None*.

        Unlike :meth:`aimodel`, this does NOT fall back to the user's
        configured Default Model.  Used by provider/model ``active_call_count``
        accounting, where resolving the default would recurse through the
        model picker (picker -> ``_provider_is_throttled`` ->
        ``active_call_count``).
        """
        model = self._get_session_setting("aimodel")
        return model if isinstance(model, AiModel) else None

    def _default_aimodel(self) -> AiModel | None:
        """Resolve the user's Default Model preference to an :class:`AiModel`."""
        from runtime.settings import get_default_model_name
        from runtime.session.aimodel_picker import pick_aimodel

        name = get_default_model_name()
        if not name:
            return None
        try:
            return pick_aimodel(name)
        except Exception:
            return None

    def set_aimodel(self, model: AiModel | None) -> None:
        """Override the AI model setting (creates a new version)."""
        self._set_session_setting("aimodel", model)

    def set_aimodel_by_name(self, name: str) -> AiModel | None:
        """Pin this session to a concrete provider for canonical model *name*.

        Chooses a provider via the shared picker (preferring usable, least
        throttled/loaded members), then persists the choice.  Returns the
        chosen :class:`AiModel`, or *None* when no usable row exists.
        """
        from runtime.session.aimodel_picker import pick_aimodel

        model = pick_aimodel(name)
        if model is not None:
            self.set_aimodel(model)
        return model

    def set_aimodel_by_provider(self, name: str, provider_id: int) -> AiModel | None:
        """Pin this session to an exact (provider, model) pair.

        Used by the composer dropdown's provider chips to select a specific
        provider for a canonical model *name*.  Prefers an enabled row whose
        provider has a usable key; falls back to the first enabled row so a
        keyless provider can still be pinned explicitly.
        """
        rows = list(
            AiModel.objects.filter(name=name, api_provider_id=provider_id, enabled=True)
        )
        if not rows:
            return None
        usable = []
        for row in rows:
            if row.api_provider.api_keys.filter(enabled=True).exists() or '"default_api_key"' in (row.api_provider.data or {}):
                usable.append(row)
        model = (usable or rows)[0]
        self.set_aimodel(model)
        return model

    # ------------------------------------------------------------------
    # Rate-limit key policy  (per-session API-key stickiness)
    # ------------------------------------------------------------------

    def preferred_api_key(self) -> Any:
        """The API key this session explicitly sticks to (user's "Switch key"
        choice, or the key adopted by auto-failover).  *None* when unset.

        Re-fetched from the DB so a cooldown written since the FK was cached
        is always visible.
        """
        session_settings = self.get_version_model().session_settings
        if not session_settings or not session_settings.preferred_api_key_id:
            return None
        from server.models.providers.api_key import ApiKey

        try:
            return ApiKey.objects.get(pk=session_settings.preferred_api_key_id)
        except ApiKey.DoesNotExist:
            return None

    def set_preferred_api_key(self, key: Any) -> None:
        """Persist the session's stick-to key (creates a new version)."""
        self._set_session_setting("preferred_api_key", key)

    def clear_preferred_api_key(self) -> None:
        """Drop the session's stick-to key."""
        settings = self.get_version_model().session_settings
        if settings and settings.preferred_api_key_id:
            self._set_session_setting("preferred_api_key", None)

    def current_provider_api_key(self, aimodel: Any) -> Any:
        """The key this session currently uses for *aimodel*'s provider.

        The explicit sticky key wins; otherwise the most recent Query that
        ran against this provider tells us which key the session is on.
        """
        preferred = self.preferred_api_key()
        if preferred is not None and preferred.api_provider_id == aimodel.api_provider_id:
            return preferred
        from server.models.queries.query import Query

        latest = (
            Query.objects.filter(
                session=self.model,
                apikey__isnull=False,
                apikey__api_provider=aimodel.api_provider,
            )
            .order_by("-pk")
            .only("apikey")
            .first()
        )
        return latest.apikey if latest is not None else None

    def auto_failover_keys_enabled(self) -> bool:
        """Return whether this session auto-switches API keys when one cools."""
        settings = self.get_version_model().session_settings
        if settings and settings.auto_failover_keys is not None:
            return bool(settings.auto_failover_keys)
        return False

    def set_auto_failover_keys(self, enabled: bool) -> None:
        """Enable/disable automatic key failover for this session."""
        self._set_session_setting("auto_failover_keys", bool(enabled))

    def key_max_wait_seconds(self) -> int:
        """Maximum acceptable key-cooldown wait; 0 = no limit (always wait)."""
        settings = self.get_version_model().session_settings
        if settings and settings.max_rate_limit_wait_seconds is not None:
            return int(settings.max_rate_limit_wait_seconds)
        return 0

    def set_key_max_wait_seconds(self, seconds: int | None) -> None:
        """Set the max wait before auto-failover (0/None = no limit)."""
        self._set_session_setting("max_rate_limit_wait_seconds", seconds)

    def key_failover_policy(self) -> Any:
        """The rate-limit key policy (auto-failover flag + max wait)."""
        from runtime.rate_limiter import KeyFailoverPolicy

        return KeyFailoverPolicy(
            auto_failover=self.auto_failover_keys_enabled(),
            max_wait_seconds=self.key_max_wait_seconds(),
        )

    @property
    def reasoning_effort(self) -> ReasoningEffort:
        """Return the resolved reasoning effort (defaults to NONE)."""
        return self._get_session_setting("reasoning_effort") or ReasoningEffort.NONE

    def set_reasoning_effort(self, value: ReasoningEffort) -> None:
        """Override the reasoning effort setting (creates a new version)."""
        self._set_session_setting("reasoning_effort", value)

    def set_scheduler_strategy(self, value: str | None) -> None:
        """Override the scheduler strategy setting (creates a new version)."""
        self._set_session_setting("scheduler_strategy", value)

    def set_tool_call_syntax(self, value: str | None) -> None:
        """Override the tool call syntax setting (creates a new version)."""
        self._set_session_setting("tool_call_syntax", value)

    def set_subagentResultDelivery(self, value: str | None) -> None:
        """Override the subagent result delivery setting (creates a new version)."""
        self._set_session_setting("subagentResultDelivery", value)

    def set_max_retries(self, value: int | None) -> None:
        """Override the max retries setting (creates a new version)."""
        self._set_session_setting("max_retries", value)

    def set_max_turns(self, value: int | None) -> None:
        """Override the max turns setting (creates a new version)."""
        self._set_session_setting("max_turns", value)

    def set_max_unattended_turns(self, value: int | None) -> None:
        """Override the max unattended turns setting (creates a new version)."""
        self._set_session_setting("max_unattended_turns", value)
    def set_precision(self, value: int | None) -> None:
        """Override the precision setting (creates a new version)."""
        self._set_session_setting("precision", value)


    def set_max_history_messages(self, value: int | None) -> None:
        """Override the max history messages setting (creates a new version)."""
        self._set_session_setting("max_history_messages", value)

    def set_priority(self, value: int | None) -> None:
        """Override the priority setting (creates a new version)."""
        self._set_session_setting("priority", value)

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
        from runtime.events import publish_model_event

        self.model.turn_count = self.model.turn_count + 1
        SessionModel.objects.filter(pk=self.model.pk).update(turn_count=self.model.turn_count)
        publish_model_event(self.model, "update")

    def reset_turn_count(self) -> None:
        """Reset the turn counter to zero."""
        SessionModel.objects.filter(pk=self.model.pk).update(turn_count=0)

    @property
    def max_unattended_turns(self) -> int:
        """Return the resolved max unattended turns."""
        return self._get_session_setting("max_unattended_turns")

    @property
    def precision(self) -> int:
        """Return precision"""
        return self._get_session_setting("precision")

    @property
    def current_unattended_turn_count(self) -> int:
        """Return the current unattended turn count."""
        self.model.refresh_from_db()
        return self.model.unattended_turn_count

    def count_unattended_turn(self) -> None:
        """Increment the unattended turn counter."""
        from runtime.events import publish_model_event

        self.model.unattended_turn_count = self.model.unattended_turn_count + 1
        SessionModel.objects.filter(pk=self.model.pk).update(unattended_turn_count=self.model.unattended_turn_count)
        publish_model_event(self.model, "update")

    def reset_unattended_turn_count(self) -> None:
        """Reset the unattended turn counter to zero."""
        try:
            SessionModel.objects.filter(pk=self.model.pk).update(unattended_turn_count=0)
        except Exception as e:
            print("Failed to update", e)

    @property
    def max_history_messages(self) -> int:
        """Return the resolved max history messages."""
        return self._get_session_setting("max_history_messages") or 0

    @property
    def auto_compact_limit(self) -> int:
        """Token threshold triggering auto-compaction (0 = disabled)."""
        return self._get_session_setting("auto_compact_limit") or 0

    @property
    def compact_size_limit(self) -> int:
        """Target token count to compact down to."""
        return self._get_session_setting("compact_size_limit") or 0

    @property
    def priority(self) -> int:
        """Return the resolved scheduling priority."""
        return self._get_session_setting("priority")

    def needs_approval(self) -> bool:
        """Return True if session has hit the unattended turn limit."""
        try:
            if self.max_unattended_turns and self.current_unattended_turn_count >= self.max_unattended_turns:
                return True
        except (TypeError, AttributeError):
            pass
        return False

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
    def inherit_system_prompt(self) -> bool:
        """Return whether this session's agent inherits parent system prompts."""
        return bool(self._get_session_setting("inherit_system_prompt"))

    @property
    def autoload(self) -> dict | None:
        """Return the resolved AGENTS.md autoload config (or *None*)."""
        value = self._get_session_setting("autoload")
        return dict(value) if isinstance(value, dict) else None

    @property
    def guidance_file_index_limit(self) -> int | None:
        """Return the resolved guidance-file index cap override (or *None*)."""
        return self._get_session_setting("guidance_file_index_limit")

    @property
    def load_guidance_file_index(self) -> bool | None:
        """Return the resolved guidance-file index toggle override (or *None*)."""
        return self._get_session_setting("load_guidance_file_index")

    @property
    def access(self) -> dict | None:
        """Return the resolved filesystem access policy block, if any."""
        return self._get_session_setting("access")

    @property
    def system_prompt_chain(self) -> list[str]:
        """Return all system prompts in inheritance order.

        When inheritSystemPrompt is enabled, returns prompts from parent
        agents first, then the current agent's prompt. Otherwise returns
        just the current agent's prompt.
        """
        return self.agent.system_prompt_chain

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
        if name not in self.allowedCommandNames:
            return None
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
        if name not in self.allowedTaskNames:
            return None
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
        if name not in self.allowedToolNames:
            return None
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
        session_settings = self.get_version_model().session_settings
        if not session_settings:  # we overwrite nothing, use agents profile
            return self.agent.get_agent_setting(name)

        # we might overwrite agent profile values
        session_settings_value = getattr(session_settings, name)
        if session_settings_value is None:  # we dont..
            return self.agent.get_agent_setting(name)

        if isinstance(session_settings_value, (str, int, bool, float, GenericContent)):
            return session_settings_value

        if isinstance(session_settings_value, (list,)):
            if "+" not in session_settings_value:  # overwrite parent list
                return session_settings_value
            extend_at_index = session_settings_value.index("+")
            session_settings_value[extend_at_index:extend_at_index + 1] = self.agent.get_agent_setting(name)
        elif isinstance(session_settings_value, dict):
            return session_settings_value
        elif isinstance(session_settings_value, AiModel): 
            return session_settings_value
        else:
            raise Exception(
                f"_get_session_setting does not yet support type of '{name}': "
                f"{type(session_settings_value)}"
            )
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
        
        print("_set_session_setting", name, value)
        new_session_setting.pk = None
        new_session_setting.created_at = None
        setattr(new_session_setting, name, value)
        new_session_setting.save()
        session_version_model.pk = None
        session_version_model.created_at = None
        session_version_model.version_number += 1
        session_version_model.session_settings = new_session_setting
        session_version_model.save()
        print(session_version_model.pk)
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
        return self.model.latest_session_version

    def is_newest_version(self):
        if self._pinned_session_version:
            return self._pinned_session_version == self.model.latest_session_version
        return True
     

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    def add_user_message(self, parts: List[Dict] | None = None, force: bool = False) -> Any:
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
        force : bool
            If True, bypass the scheduler strategy and dispatch immediately.
        """
        if not parts:
            raise Exception("No message or message parts provided")

        self._guard_image_parts_against_non_vision_model(parts)

        self.set_is_active(True)

        bound_task, call_kwargs, _ = self._resolve_inbound_task(parts)

        if not force:
            strategy = self.scheduler_strategy
            if strategy == "queue":
                if self._has_active_call():
                    return self._park_call(bound_task, call_kwargs)
                return bound_task.delay(**call_kwargs)
            if strategy == "interrupt":
                if self._has_active_call():
                    self.stop_generation()
                return bound_task.delay(**call_kwargs)
            if strategy == "merge":
                if self._has_active_call():
                    return self.steer_message(parts)

        return bound_task.delay(**call_kwargs)

    def _resolve_inbound_task(self, parts: List[Dict]) -> tuple:
        """Parse inbound *parts* into ``(bound_task, call_kwargs, is_command)``.

        A leading ``/`` in the first part routes to ``ingest_slash_command``;
        everything else routes to ``ingest_user_message``.
        """
        is_command = False
        cmd = ""
        parsed_kwargs: dict = {}

        if parts[0] and parts[0].get("content", [None, ])[0] == "/":
            cmd = parts[0].get("content", [None, ]).split(None, 1)[0][1:].strip()
            bound_cmd = self.get_command(cmd)
            if not bound_cmd:
                bound_cmd = self.get_tool(cmd)
            if bound_cmd:
                is_command = True
                full_cmd_str = "".join([part["content"] for part in parts]).strip() if parts else ""
                cmd_payload = full_cmd_str[1 + len(cmd):].strip()
                try:
                    parsed_kwargs = json.loads(cmd_payload)
                except (json.JSONDecodeError, TypeError):
                    try:
                        _payload_ast_tree = ast.parse(f"f({cmd_payload})")
                        call = _payload_ast_tree.body[0].value if _payload_ast_tree.body else None
                        parsed_kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords} if call else {}
                    except SyntaxError:
                        raise ValueError(
                            f"Could not parse arguments for /{cmd}. "
                            f"Expected JSON or Python keyword arguments, got: {cmd_payload!r}"
                        )

        if is_command:
            bound_task = self.get_task("ingest_slash_command")
            call_kwargs: dict = dict(command_name=cmd, **parsed_kwargs)
        else:
            bound_task = self.get_task("ingest_user_message")
            call_kwargs = dict(parts=parts)
        return bound_task, call_kwargs, is_command

    def _park_call(self, bound_task, call_kwargs):
        """Create the call parked at ``WAITING_QUEUE``.

        The parked call waits while a live turn runs and is released FIFO
        when the turn ends (drain in ``_on_taskcall_ended`` + tick fallback).
        """
        with transaction.atomic():
            SessionModel.objects.select_for_update().get(pk=self.model.pk)
            ti = bound_task.instance(kwargs=call_kwargs)
            taskcall = ti.create_call(kwargs=call_kwargs)
            from server.models.tasks.agent_task_call import AgentTaskCall as _ATC
            from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
            _ATC.objects.filter(pk=taskcall.pk).update(
                status=TaskCallStatus.WAITING,
                status_detail=TaskCallStatusDetail.WAITING_QUEUE,
            )
            return taskcall

    def queue_message(self, parts: List[Dict] | None = None) -> Any:
        """Park *parts* to run after the live turn finishes ("Queue message").

        Parks whenever a turn is active, regardless of scheduler strategy;
        dispatches immediately when idle.
        """
        if not parts:
            raise Exception("No message or message parts provided")

        self._guard_image_parts_against_non_vision_model(parts)

        self.set_is_active(True)

        bound_task, call_kwargs, _ = self._resolve_inbound_task(parts)
        if self._has_active_call():
            return self._park_call(bound_task, call_kwargs)
        return bound_task.delay(**call_kwargs)

    def steer_message(self, parts: List[Dict] | None = None) -> Any:
        """Insert *parts* into the running turn ("Steer current response").

        Persists the user message immediately so the next ``process_turn``
        of the live chain picks it up via history.  Slash commands bypass
        steering and dispatch immediately (their chain builds no LLM query).
        When the turn ended in the meantime, a fresh ``process_turn`` is
        dispatched for the message instead of leaving it unprocessed.
        """
        if not parts:
            raise Exception("No message or message parts provided")

        self._guard_image_parts_against_non_vision_model(parts)

        self.set_is_active(True)

        bound_task, call_kwargs, is_command = self._resolve_inbound_task(parts)
        if is_command:
            return bound_task.delay(**call_kwargs)

        process_turn = self.get_task("process_turn")
        if process_turn is None:
            return bound_task.delay(**call_kwargs)

        from server.models.enums.message_enums import MessageRole as _MsgRole
        from server.models.message import Message as _Msg
        from runtime.events import publish_model_event

        session_version = self.get_version_model()
        prev_message = self.get_last_message()
        message = _Msg.objects.create(
            role=_MsgRole.USER,
            session=session_version.session,
            session_version=session_version,
            prev_message=prev_message,
        )
        for part in parts:
            message.add_part(
                type=part["type"],
                content_type=part["content_type"],
                content=part["content"],
                template_data=part.get("template_data", None),
                tool_call=part.get("tool_call", None),
            )
        publish_model_event(message, "create")

        if not self._has_active_call():
            # Turn ended between the check and the insert — start a fresh
            # turn for the message instead of leaving it unprocessed.
            return self._dispatch_steer_continuation(process_turn, message)
        return message

    def _dispatch_steer_continuation(self, process_turn, message) -> Any:
        """Dispatch exactly one continuation turn for a steered message.

        The idle check above can lose a race with a concurrently starting
        turn (e.g. the tick releasing a parked message in the same moment).
        Two live turns would collide on the session's single ``Query`` —
        so when a sibling turn call exists right after our dispatch and
        ours hasn't started yet, ours is re-parked at ``WAITING_QUEUE``
        instead of running in parallel: the tick/session drain releases it
        FIFO once the sibling ends. Sequential, nothing lost (our trigger
        message is intact), never parallel.

        A sibling on the same task instance usually never gets this far:
        ``start_new_taskrun`` already holds the second call at
        ``WAITING_QUEUE`` (``limit_per_instance_parallel_runs=1``) — the
        re-park below then just re-asserts that state.
        """
        from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
        from server.models.tasks.agent_task_call import AgentTaskCall as _ATC

        new_call = process_turn.delay(message=message)
        sibling_live = (
            _ATC.objects.filter(
                session=self.model,
                task_definition__name__in=[
                    "ingest_user_message",
                    "ingest_slash_command",
                    "process_turn",
                    "compact_turn",
                ],
            )
            .exclude(status=TaskCallStatus.ENDED)
            .exclude(pk=new_call.pk)
            .exclude(status_detail=TaskCallStatusDetail.WAITING_QUEUE)
            .exists()
        )
        if not sibling_live:
            return new_call
        # Sibling turn is really running (not just parked) — park ours
        # behind it. Only valid while ours hasn't started; an already
        # running call is left alone (never observed in practice — a
        # worker cannot pick the run up within this window).
        _ATC.objects.filter(
            pk=new_call.pk,
            status_detail__in=[
                TaskCallStatusDetail.NEW,
                TaskCallStatusDetail.WAITING_DEPENDENCY,
                TaskCallStatusDetail.WAITING_QUEUE,
            ],
        ).update(
            status=TaskCallStatus.WAITING,
            status_detail=TaskCallStatusDetail.WAITING_QUEUE,
        )
        return new_call

    def is_busy(self) -> bool:
        """Return True while a turn is running or pending for this session."""
        return self._has_active_call()

    def stop_generation(self) -> int:
        """Cancel the currently running/pending turn, if any ("Stop generation").

        Cancels the whole root trees (ingest + ``process_turn`` children, so
        in-flight LLM streaming cannot continue the turn) and fails open
        queries so query cards refresh.  Parked queue entries are pending
        turn calls too, so they are cancelled as well (full stop — use the
        queue card to drop individual messages).  Safe no-op when idle.
        Returns the number of active calls stopped.
        """
        from server.models.enums.task_enums import TaskCallStatus
        from server.models.tasks.agent_task_call import AgentTaskCall
        from runtime.tasks.call_scheduler import CallScheduler

        active = list(
            AgentTaskCall.objects.filter(
                session=self.model,
                task_definition__name__in=[
                    "ingest_user_message",
                    "ingest_slash_command",
                    "process_turn",
                    "compact_turn",
                ],
            ).exclude(status=TaskCallStatus.ENDED).values_list("pk", "session_root_task_id")
        )
        roots = {root_id or pk for pk, root_id in active}
        for root_id in roots:
            CallScheduler.cancel_root_tasktree(root_id)

        from server.models.queries.query import Query, QueryStatus
        from runtime.events import publish_model_event

        for query in Query.objects.filter(
            session=self.model,
            status__in=[QueryStatus.WAITING, QueryStatus.ACTIVE],
        ):
            Query.objects.filter(pk=query.pk).update(status=QueryStatus.FAILURE)
            try:
                publish_model_event(Query.objects.get(pk=query.pk), "update")
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        return len(active)

    def _guard_image_parts_against_non_vision_model(self, parts: list[Dict]) -> None:
        """Block image parts when the selected model cannot see images.

        Providers bill image input against vision models only; sending an
        ``image_url`` block to a text-only model either errors or silently
        drops the image.  Raise a clear error naming a few vision-capable
        models so the user can switch instead of losing the image silently.
        """
        if not any(part.get("content_type", "").upper() == "IMAGE" for part in parts):
            return

        aimodel = self.aimodel
        if aimodel is not None and aimodel.vision:
            return

        model_label = "None"
        if aimodel is not None:
            model_label = f"{aimodel.name} ({aimodel.provider_model_id})"

        vision_models = list(
            AiModel.objects.filter(enabled=True, vision=True)
            .exclude(api_provider__enabled=False)
            .values_list("name", flat=True)
            .order_by("name")[:6]
        )
        suggestions = ", ".join(vision_models) if vision_models else "(no vision models enabled)"
        raise TypeError(
            f"Cannot attach images: the selected model {model_label} is not vision-capable. "
            f"Switch to a vision-capable model in the composer (e.g. {suggestions}) to send images."
        )

    def set_is_active(self, new_value: bool) -> None:
        """Mark the session active and stamp the last-activity timestamp.

        Any incoming message (user or subagent) reactivates an inactive
        session and refreshes ``last_active_at``, which the sidebar and
        ``list_subsessions`` use to decide which inactive sessions to show.
        """
        from django.utils import timezone
        from runtime.events import publish_model_event
        if new_value == self.model.is_active:
            return

        now = timezone.now()
        was_inactive = not self.model.is_active
        SessionModel.objects.filter(pk=self.model.pk).update(
            is_active=new_value,
            last_active_at=now,
        )
        self.model.is_active = new_value
        publish_model_event(self.model, "update")

    def _has_active_call(self) -> bool:
        """Return True if there is a non-ended ingest or process_turn call
        for this session — covers both user-initiated and agent-continuation flows."""
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.enums.task_enums import TaskCallStatus
        return AgentTaskCall.objects.filter(
            session=self.model,
            task_definition__name__in=[
                "ingest_user_message",
                "ingest_slash_command",
                "process_turn",
                "compact_turn",
            ],
        ).exclude(status=TaskCallStatus.ENDED).exists()

    def get_messages(self) -> Any:
        """Return all messages for this session."""
        return Message.objects.filter(session_version__session=self.model)

    def get_last_message(self) -> Message | None:
        """Return the newest message of this session's own chain.

        A message is a tail when it has no ``next_messages`` *in this
        session*.  Forks and subtasks anchor their first message to a parent
        message via ``prev_message`` (cross-session), so a plain
        ``filter(next_messages=None)`` would see those children and hide the
        parent's real tail.
        """
        return (
            self.get_messages()
            .exclude(next_messages__session=self.model)
            .last()
        )

    def context_usage(self) -> Dict[str, Any]:
        """Return the session's current context-window usage.

        Source of truth is the latest ``SUCCESS`` query: ``Query.tokens`` is
        recalibrated to the backend-reported ``prompt_tokens`` on
        ``Response.save()``, so it is an accurate count, not an estimate.
        Falls back to the newest query of any status (estimates) when no
        successful query exists yet, and to ``has_data=False`` when the
        session has never queried.

        Returns a dict with ``used_tokens`` (prompt), ``completion_tokens``
        (latest response output), ``context_length`` (model window, 0 when
        unknown), ``percent`` (0-100+, >100 means over window).
        """
        empty: Dict[str, Any] = {
            "tokens_send": 0,
            "tokens_received": 0,
            "tokens_cached": 0,
            "cache_hit_rate": 0,
            "tokens_reasoning": 0,
            "tokens_reasoning_percent": 0,
            "max_context_tokens": 0,
            "used_context_tokens": 0,
            "used_context_percent": 0,
        }
        try:
            successful = Response.objects.filter(session=self.model, status=ResponseStatus.SUCCESS)
            latest_response = successful.order_by("-id").first()
            if latest_response is None:
                return empty

            # Single DB-side aggregation instead of fetching every row and
            # summing in Python: one query, constant memory, no N+1.
            totals = successful.aggregate(
                tokens_send=Sum("prompt_tokens"),
                tokens_received=Sum("completion_tokens"),
                tokens_cached=Sum("cached_tokens"),
                tokens_reasoning=Sum("reasoning_tokens"),
            )
            tokens_send = int(totals["tokens_send"] or 0)
            tokens_received = int(totals["tokens_received"] or 0)
            tokens_cached = int(totals["tokens_cached"] or 0)
            tokens_reasoning = int(totals["tokens_reasoning"] or 0)

            aimodel = self.aimodel
            max_context_tokens = int(getattr(aimodel, "context_length", 0) or 0) if aimodel else 0
            if not max_context_tokens:
                max_context_tokens = self.auto_compact_limit
            elif (self.auto_compact_limit or 0) > 0:
                max_context_tokens = min(max_context_tokens, self.auto_compact_limit)

            return {
                "tokens_send": tokens_send,
                "tokens_received": tokens_received,
                "tokens_cached": tokens_cached,
                "cache_hit_rate": (100 / tokens_send * tokens_cached) if tokens_send > 0 else 0,
                "tokens_reasoning": tokens_reasoning,
                "tokens_reasoning_percent": (100 / tokens_received * tokens_reasoning) if tokens_received > 0 else 0,
                "max_context_tokens": max_context_tokens,
                "used_context_tokens": latest_response.prompt_tokens,
                "used_context_percent": (latest_response.prompt_tokens / max_context_tokens * 100.0) if max_context_tokens > 0 else 0.0,
            }
        except Exception:  # pylint: disable=broad-exception-caught
            return empty
