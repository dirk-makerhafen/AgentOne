from __future__ import annotations
import ast
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List

from django.db import transaction
from django.db.models import Sum

from runtime.agents.agent import Agent, is_name_disallowed
from runtime.session.messages import default_type_for_role, normalize_messages
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
from server.models.workspace import WorkspaceModel

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
        """Return the runtime Agent associated with this session.

        Respects ``pinned_agent_version`` so a ``reload_all`` (new
        AgentVersion + tool versions) does not change the system prompt or
        tool schemas mid-conversation — which would invalidate the provider
        KV/prompt cache prefix.  New sessions and post-compaction upgrades
        pin to the latest version explicitly.
        """
        sv = self.get_version_model()
        try:
            pinned = sv.pinned_agent_version
        except Exception:  # pylint: disable=broad-exception-caught
            pinned = None
        if pinned is not None:
            try:
                # Guard against a stale pin from before a set_agent switch
                # (pinned belongs to a different AgentModel than the session).
                if getattr(pinned, "agent_id", None) == getattr(sv, "agent_id", None):
                    return pinned.get_runtime()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        return sv.agent.get_runtime()

    def set_agent(self, agent: Any) -> None:
        """Set the agent for this session (creates a new version).

        Also re-pins to the new agent's latest version so the session does
        not keep serving the previous agent's tools/prompts via a stale
        ``pinned_agent_version``.
        """
        self._set_session_property("agent", agent)
        try:
            sv = self.get_version_model()
            latest = sv.agent.latest_agent_version
            pinned = sv.pinned_agent_version
            if latest is not None and (pinned is None or pinned.pk != latest.pk or pinned.agent_id != sv.agent_id):
                sv.pk = None
                sv.created_at = None
                sv.version_number += 1
                sv.pinned_agent_version = latest
                sv.save()
                self.model.latest_session_version = sv
                self.model.save()
                if self._pinned_session_version is not None:
                    self._pinned_session_version = sv
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    @property
    def pinned_agent_version(self) -> Any | None:
        """The AgentVersion this session is pinned to, or *None* (follow latest)."""
        try:
            return self.get_version_model().pinned_agent_version
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    @property
    def latest_agent_version(self) -> Any | None:
        """The current latest AgentVersion for this session's agent, or *None*."""
        try:
            return self.get_version_model().agent.latest_agent_version
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def has_agent_update(self) -> bool:
        """True when a newer AgentVersion exists than the pinned one.

        ``pinned=None`` means follow-latest (legacy sessions) — no banner.
        """
        try:
            sv = self.get_version_model()
            pinned = sv.pinned_agent_version
            if pinned is None:
                return False
            latest = sv.agent.latest_agent_version
            if latest is None:
                return False
            return pinned.pk != latest.pk
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    def upgrade_to_latest_agent(self) -> bool:
        """Re-pin this session to the latest AgentVersion (copy-on-write).

        Creates a new SessionVersion preserving everything except
        ``pinned_agent_version``, which is set to the agent's current
        latest.  Safe to call after a compaction boundary (new KV-cache
        segment) or from the UI upgrade button.  Returns True when a new
        version was created, False when already current.
        """
        sv = self.get_version_model()
        try:
            latest = sv.agent.latest_agent_version
        except Exception:  # pylint: disable=broad-exception-caught
            return False
        if latest is None:
            return False
        try:
            pinned = sv.pinned_agent_version
        except Exception:  # pylint: disable=broad-exception-caught
            pinned = None
        if pinned is not None and pinned.pk == latest.pk:
            return False
        # Copy-on-write: SessionVersion rows are immutable (save() forbids
        # updates), so clone via pk=None like _set_session_property.
        sv.pk = None
        sv.created_at = None
        sv.version_number += 1
        sv.pinned_agent_version = latest
        sv.save()
        self.model.latest_session_version = sv
        self.model.save()
        # Keep this wrapper's pinned pointer coherent when it wraps a
        # specific version object.
        if self._pinned_session_version is not None:
            self._pinned_session_version = sv
        return True

    # ------------------------------------------------------------------
    # Session-level properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the session name."""
        return self.model.name

    @property
    def group_key(self) -> str:
        """Return the non-unique grouping key (``""`` when unset)."""
        return self.model.group_key

    def set_group_key(self, value: str) -> None:
        """Set the grouping key without minting a new session version."""
        self.model.atomic_update(group_key=value or "")

    @property
    def session_type(self) -> str:
        """Return the session type (SessionType value)."""
        return self.model.session_type

    @property
    def description(self) -> str:
        """Return the description from the active session version."""
        return self.get_version_model().description

    @property
    def workspace(self) -> WorkspaceModel | None:
        """Return the workspace from the active session version."""
        return self.get_version_model().workspace

    def get_project(self) -> Any | None:
        """Return the project this session belongs to, or *None* for global."""
        try:
            return self.model.parent_project
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    @property
    def private_dir(self) -> Any:
        """Return this session's private folder path (pure, no I/O).

        Lives at ``<AGENTONE_SESSIONS_DIR>/<session_pk>/``.  Each session
        — including subsessions — gets its own folder.
        """
        from runtime.session_folder import session_dir

        return session_dir(self)

    def ensure_private_dir(self) -> Any:
        """Create this session's private folder if missing and return it."""
        from runtime.session_folder import ensure_session_dir

        return ensure_session_dir(self)

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
        self.model.atomic_update(turn_count=self.model.turn_count + 1)

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
        self.model.atomic_update(unattended_turn_count=self.model.unattended_turn_count + 1)

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
    def auto_compact_max_tokens(self) -> int:
        """Hard token threshold triggering reactive auto-compaction (0 = disabled)."""
        return self._get_session_setting("auto_compact_max_tokens") or 0

    @property
    def auto_compact_min_tokens(self) -> int:
        """Context floor for idle-triggered compaction (0 = idle compaction disabled)."""
        return self._get_session_setting("auto_compact_min_tokens") or 0

    @property
    def auto_compact_idle_seconds(self) -> int:
        """Idle seconds after which an oversized session is compacted (0 = disabled)."""
        return self._get_session_setting("auto_compact_idle_seconds") or 0

    @property
    def auto_compact_keep_percent(self) -> int | None:
        """Percentage of newest tokens kept in full on compaction.

        *None* (unset) means the default (15); an explicit ``0`` keeps
        nothing — the whole range is compacted. No ``or 0`` coercion here:
        ``history_limiter`` must tell unset apart from explicit zero.
        """
        return self._get_session_setting("auto_compact_keep_percent")

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
    def session_bootstrap_chain(self) -> list[str]:
        """Return inherited ``sessionBootstrap`` templates, parents first."""
        return self.agent.session_bootstrap_chain

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

    @property
    def is_paused(self) -> bool:
        """Return whether the session is soft-paused (fresh read).

        Reads straight from the DB so workers with a stale cached model
        still observe a pause set from the UI/API.
        """
        from server.models.sessions.session import SessionModel as _SM

        try:
            return bool(
                _SM.objects.filter(pk=self.model.pk)
                .values_list("is_paused", flat=True)
                .first()
            )
        except Exception:  # pylint: disable=broad-exception-caught
            return bool(getattr(self.model, "is_paused", False))

    def pause(self) -> None:
        """Soft-pause this session: finish active runs, park everything else.

        Active ``ACTIVE_RUNNING`` taskruns are never aborted — they run to
        completion.  Every *new* run creation funnels through
        ``CallScheduler.start_new_taskrun``, which refuses to pick up calls
        while paused, so continuations (next ``process_turn`` link,
        cron/data-flow/subagent deliveries, retries, rate-limit releases)
        park in ``WAITING_QUEUE``/``WAITING_RETRY``/``WAITING_RATELIMIT``
        until :meth:`resume`.  No hooks fire; ``is_active`` is untouched.
        """
        try:
            self.model.atomic_update(is_paused=True)
        except Exception:  # pylint: disable=broad-exception-caught
            from server.models.sessions.session import SessionModel as _SM

            _SM.objects.filter(pk=self.model.pk).update(is_paused=True)
            try:
                self.model.is_paused = True
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def resume(self) -> None:
        """Clear a soft-pause and immediately release parked work.

        Unsets the flag first, then releases the head of the session's
        ``WAITING_QUEUE`` (FIFO gate honoured).  Rate-limited/retry/scheduled
        calls are picked up by the regular 10s tick; the queue head is
        released here so the UI feels instant.
        """
        try:
            self.model.atomic_update(is_paused=False)
        except Exception:  # pylint: disable=broad-exception-caught
            from server.models.sessions.session import SessionModel as _SM

            _SM.objects.filter(pk=self.model.pk).update(is_paused=False)
            try:
                self.model.is_paused = False
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        try:
            from runtime.tasks.call_scheduler import CallScheduler

            CallScheduler._release_next_queued_call(self.model)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

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
    # Child-session creation
    # ------------------------------------------------------------------

    def resolve_agent_version(self, name: str | None = None) -> AgentVersionModel | None:
        """Resolve an agent version by name.

        Prefers an allowed subagent of this session; falls back to a top-level
        agent looked up by name — so framework/internal agents that are
        deliberately excluded from the subagent allowlist (e.g. ``baseagent``,
        ``approval_decider``) can still be spawned by name. Returns ``None``
        when neither exists.
        """
        name = name or self.agent.name
        if (av := self.get_subagent(name)):
            return av
        from server.models.agents.agent import AgentModel

        model = AgentModel.objects.filter(name=name).first()
        return model.get_runtime().get_version_model() if model else None

    def fork(  # pylint: disable=too-many-arguments
        self,
        *,
        name: str,
        description: str = "",
        display_name: str | None = None,
        session_type: str = "",
        group_key: str = "",
        workspace: Any = None,
        preserve_history: bool = False,
        anchor: Message | None = None,
        settings: SettingsModel | None = None,
        **settings_overrides: Any,
    ) -> "Session":
        """Create a child session running the *same* agent as this one.

        The child inherits this session's settings (with ``settings_overrides``
        applied on top) and query-template/adhoc-tool links. Use
        :meth:`spawn_subagent` to run a *different* agent's session.

        ``group_key`` is a non-unique grouping key (``domain:task``) stored on
        the child session; unlike settings it is never inherited implicitly.

        ``preserve_history`` (or an explicit ``anchor`` message) grafts the
        child's message chain onto this session's, so the child sees the
        conversation up to that point.
        """
        agent_version = self.agent.get_version_model()
        child_sv = agent_version.get_or_create_session(
            name=name,
            description=description,
            display_name=display_name,
            workspace=workspace if workspace is not None else self.workspace,
            parent_session_version=self.get_version_model(),
            session_type=session_type,
            group_key=group_key,
            settings_inherit=True,
            settings=settings,
            settings_overrides=settings_overrides or None,
            inherit_links=True,
        )
        child = Session(session_model=child_sv.session, pinned_session_version=child_sv)
        if anchor is None and preserve_history:
            anchor = self.get_last_message()
        if anchor is not None:
            child.link_history_to(self, anchor=anchor)
        return child

    def spawn_subagent(  # pylint: disable=too-many-arguments
        self,
        agent: str | AgentVersionModel,
        *,
        name: str,
        description: str = "",
        display_name: str | None = None,
        session_type: str = "",
        group_key: str = "",
        workspace: Any = None,
        project: Any = None,
        settings: SettingsModel | None = None,
        allow_internal: bool = False,
        anchor: Message | None = None,
        preserve_history: bool = False,
        **settings_overrides: Any,
    ) -> "Session | None":
        """Create a child session for another agent (possibly a different one).

        *agent* may be an agent **name** or an already-resolved
        ``AgentVersionModel``. A name is resolved through this session's
        subagent allowlist (:meth:`get_subagent`); pass ``allow_internal=True``
        to additionally resolve framework/internal agents (e.g. ``baseagent``,
        ``approval_decider``) that are deliberately excluded from the allowlist
        (:meth:`resolve_agent_version`). Returns ``None`` when a name cannot be
        resolved — callers decide how to report that.

        Unlike :meth:`fork`, the child inherits **none** of this session's
        settings or links — the parent's agent-config overrides must never
        shadow the child agent's own settings. Pass ``settings`` or
        ``settings_overrides`` for anything the child explicitly needs.
        ``preserve_history`` (or an explicit ``anchor`` message) grafts the
        child's message chain onto this session's, mirroring :meth:`fork`.

        ``project`` (a ``Project`` row, optional) binds the child session to
        that project scope (``SessionModel.parent_project``) so project-scoped
        tools — e.g. the internal ``*_assistant`` collection tools — resolve
        the right collection. The runtime collection classes pass this
        automatically (e.g. via ``get_assistant_session()``).

        ``group_key`` is a non-unique grouping key (``domain:task``) stored on
        the child session, so callers can later group same-agent sessions.
        """
        if isinstance(agent, str):
            agent_version = (
                self.resolve_agent_version(agent) if allow_internal
                else self.get_subagent(agent)
            )
        else:
            agent_version = agent
        if agent_version is None:
            return None
        child_sv = agent_version.get_or_create_session(
            name=name,
            description=description,
            display_name=display_name,
            workspace=workspace if workspace is not None else self.workspace,
            parent_session_version=self.get_version_model(),
            session_type=session_type,
            group_key=group_key,
            settings_inherit=False,
            settings=settings,
            settings_overrides=settings_overrides or None,
            inherit_links=False,
        )
        child = Session(session_model=child_sv.session, pinned_session_version=child_sv)
        if project is not None:
            try:
                project_pk = project.pk
            except AttributeError:
                project_pk = None
            if project_pk is not None and child.model.parent_project_id != project_pk:
                child.model.parent_project = project
                child.model.save(update_fields=["parent_project_id"])
        if anchor is None and preserve_history:
            anchor = self.get_last_message()
        if anchor is not None:
            child.link_history_to(self, anchor=anchor)
        return child

    def link_history_to(self, parent: "Session", anchor: Message | None = None) -> Message:
        """Create a hidden anchor message so this session's chain continues
        from *parent*'s conversation at *anchor* (defaults to its last message).

        Messages added afterwards chain off this anchor automatically.
        """
        if anchor is None:
            anchor = parent.get_last_message()
        return self._persist_message(
            role="info",
            message_type="info",
            content=f"Forked from session #{parent.model.pk}.",
            hide_from_context=True,
            prev_message=anchor,
        )

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

    def _persist_message(  # pylint: disable=too-many-arguments
        self,
        *,
        role: str = "user",
        message_type: str | None = None,
        parts: List[Dict] | None = None,
        content: str | None = None,
        response: Response | None = None,
        hide_from_context: bool = False,
        pin_to_context: bool = False,
        prev_message: Message | None = None,
    ) -> Message:
        """Low-level, synchronous message creation for framework internals.

        Used only for messages that must exist *before* the caller continues
        (the hidden fork anchor in :meth:`link_history_to` and the compaction
        marker).  Everything user-facing goes through
        :meth:`add_user_message` so the scheduler and task pipeline apply.
        """
        from server.models.enums.message_enums import MessageContentType, MessagePartType

        resolved_parts: List[Dict] = []
        if content is not None:
            resolved_parts.append(
                {
                    "type": MessagePartType.MESSAGE,
                    "content_type": MessageContentType.TEXT,
                    "content": content,
                }
            )
        if parts:
            resolved_parts.extend(parts)
        if not resolved_parts:
            raise ValueError("_persist_message requires 'content' or 'parts'")

        session_version = self.get_version_model()
        if prev_message is None:
            prev_message = self.get_last_message()

        message = Message.objects.create(
            role=role,
            message_type=message_type or default_type_for_role(role),
            session=session_version.session,
            session_version=session_version,
            response=response,
            prev_message=prev_message,
            hide_from_context=hide_from_context,
            pin_to_context=pin_to_context,
        )
        for part in resolved_parts:
            message.add_part(
                type=part["type"],
                content_type=part["content_type"],
                content=part["content"],
                template_data=part.get("template_data", None),
                tool_call=part.get("tool_call", None),
            )

        # Two-phase write (see Message.save): publish only now parts exist.
        message.publish("create")
        return message

    def add_user_message(self, message: Any = None, force: bool = False, execute_turn: bool = True) -> Any:
        """
        Ingest a user message into this session.

        *message* accepts the flexible spec documented in
        :func:`runtime.session.messages.normalize_messages`: a bare string, a
        list of strings / part dicts (one message, many parts) or a list of
        message dicts (mixed roles).  A single user message whose first part
        starts with ``/`` is routed as a slash command.

        The session scheduler strategy (queue / interrupt / merge) is honoured
        unless *force* is True.  When *execute_turn* is False the message(s)
        are only persisted and no ``process_turn`` is started.

        Parameters
        ----------
        message : Any
            The message spec (string, part dict(s) or message dict(s)).
        force : bool
            If True, bypass the scheduler strategy and dispatch immediately.
        execute_turn : bool
            Whether to start a ``process_turn`` for the message(s).
        """
        messages = self._prepare_inbound(message)

        self.set_is_active(True)

        bound_task, call_kwargs, is_command = self._resolve_inbound_task(messages, execute_turn)

        if not force:
            strategy = self.scheduler_strategy
            # Pure persists (compaction INFO notices, hook anchors) start no
            # turn and fire no query, so there is nothing to serialize — they
            # must land immediately even while tool work is live.  Without
            # this carve-out the widened liveness check below would park
            # them and they would surface late and out of chain order.
            persist_only = (execute_turn is False) and not is_command
            if not persist_only and strategy in ("queue", "batch"):
                if self._has_active_call():
                    # TODO(batch): coalesce parked messages into a single turn
                    # (persist all, run one turn on the last) instead of FIFO.
                    return self._park_call(bound_task, call_kwargs)
                return bound_task.delay(**call_kwargs)
            if not persist_only and strategy == "interrupt":
                if self._has_active_call():
                    self.stop_generation()
                return bound_task.delay(**call_kwargs)
            if not persist_only and strategy == "merge":
                if self._has_active_call():
                    return self.steer_message(message, execute_turn=execute_turn)

        return bound_task.delay(**call_kwargs)

    def _prepare_inbound(self, message: Any) -> List[Dict]:
        """Normalize *message* and guard image parts against a non-vision model."""
        messages = normalize_messages(message)
        parts = [part for msg in messages for part in msg["parts"]]
        self._guard_image_parts_against_non_vision_model(parts)
        return messages

    def _resolve_inbound_task(self, messages: List[Dict], execute_turn: bool = True) -> tuple:
        """Resolve normalized *messages* into ``(bound_task, call_kwargs, is_command)``.

        Exactly one user message whose first part starts with ``/`` routes to
        ``ingest_slash_command``; everything else routes to
        ``ingest_user_message`` with *execute_turn* threaded through.
        """
        is_command = False
        cmd = ""
        parsed_kwargs: dict = {}

        first = messages[0]
        first_parts = first["parts"]
        is_slash = (
            len(messages) == 1
            and first["role"] == "user"
            and bool(first_parts)
            and isinstance(first_parts[0]["content"], str)
            and first_parts[0]["content"].startswith("/")
        )

        if is_slash:
            full_cmd_str = "".join(
                part["content"] for part in first_parts if isinstance(part["content"], str)
            ).strip()
            cmd = full_cmd_str.split(None, 1)[0][1:].strip()
            bound_cmd = self.get_command(cmd)
            if not bound_cmd:
                bound_cmd = self.get_tool(cmd)
            if bound_cmd:
                is_command = True
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
            call_kwargs = dict(message=messages, execute_turn=execute_turn)
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

    def queue_message(self, message: Any = None) -> Any:
        """Park *message* to run after the live turn finishes ("Queue message").

        Parks whenever a turn is active, regardless of scheduler strategy;
        dispatches immediately when idle.
        """
        messages = self._prepare_inbound(message)

        self.set_is_active(True)

        bound_task, call_kwargs, _ = self._resolve_inbound_task(messages, execute_turn=True)
        if self._has_active_call():
            return self._park_call(bound_task, call_kwargs)
        return bound_task.delay(**call_kwargs)

    def steer_message(self, message: Any = None, execute_turn: bool = True) -> Any:
        """Insert *message* into the running turn ("Steer current response").

        Persists the user message immediately so the next ``process_turn``
        of the live chain picks it up via history.  Slash commands bypass
        steering and dispatch immediately (their chain builds no LLM query).
        When the turn ended in the meantime, a fresh ``process_turn`` is
        dispatched for the message instead of leaving it unprocessed.
        """
        messages = self._prepare_inbound(message)

        self.set_is_active(True)

        bound_task, call_kwargs, is_command = self._resolve_inbound_task(messages, execute_turn=execute_turn)
        if is_command:
            return bound_task.delay(**call_kwargs)

        process_turn = self.get_task("process_turn")
        if process_turn is None:
            return bound_task.delay(**call_kwargs)

        from server.models.message import Message as _Msg

        session_version = self.get_version_model()
        prev_message = self.get_last_message()
        created = None
        for spec in messages:
            created = _Msg.objects.create(
                role=spec["role"],
                message_type=spec.get("message_type") or default_type_for_role(spec["role"]),
                session=session_version.session,
                session_version=session_version,
                prev_message=prev_message,
            )
            for part in spec["parts"]:
                created.add_part(
                    type=part["part_type"],
                    content_type=part["content_type"],
                    content=part["content"],
                    template_data=part.get("template_data", None),
                    tool_call=part.get("tool_call", None),
                )
            # Two-phase write (see Message.save): publish only now parts exist.
            created.publish("create")
            prev_message = created

        if execute_turn and not self._has_active_call():
            # Turn ended between the check and the insert — start a fresh
            # turn for the message instead of leaving it unprocessed.
            return self._dispatch_steer_continuation(process_turn, created)
        return created

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
        # Any other live session work (turn, tool call, subagent wait) —
        # not just sibling ingest calls — means a turn is really running.
        sibling_live = (
            _ATC.objects.filter(
                session=self.model,
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
        """Cancel the currently running/pending work, if any ("Stop generation").

        Cancels all non-ended root trees in the session — ingest +
        ``process_turn`` chains (so in-flight LLM streaming cannot continue
        the turn) as well as live tool/subagent work from previous turns (a
        still-running tool call would otherwise keep working under the new
        turn).  Fails open queries so query cards refresh.  Parked queue
        entries are pending turn calls too, so they are cancelled as well
        (full stop — use the queue card to drop individual messages).  Safe
        no-op when idle.  Returns the number of active calls stopped.
        """
        from server.models.enums.task_enums import TaskCallStatus
        from server.models.tasks.agent_task_call import AgentTaskCall
        from runtime.tasks.call_scheduler import CallScheduler

        active = list(
            AgentTaskCall.objects.filter(
                session=self.model,
            ).exclude(status=TaskCallStatus.ENDED).values_list("pk", "session_root_task_id")
        )
        roots = {root_id or pk for pk, root_id in active}
        for root_id in roots:
            CallScheduler.cancel_root_tasktree(root_id)

        from server.models.queries.query import Query, QueryStatus

        for query in Query.objects.filter(
            session=self.model,
            status__in=[QueryStatus.WAITING, QueryStatus.ACTIVE],
        ):
            query.atomic_update(status=QueryStatus.FAILURE)
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

    def request_end(self, reason: str = "deactivated") -> None:
        """End this session via the ``session_end`` task.

        The single deactivation path: ``set_is_active(False)`` is no longer
        called directly, so the ``session_end`` task is the anchor for
        ``after:`` intercept hooks (``docs/session-hooks.md``). Falls back to
        a direct write only if the task is not registered for this agent, so
        a missing script can never leave a session active.
        """
        task = self.get_task("session_end")
        if task is None:
            self.set_is_active(False)
            return
        task.delay(reason=reason)

    def set_is_active(self, new_value: bool) -> None:
        """Mark the session active and stamp the last-activity timestamp.

        Any incoming message (user or subagent) reactivates an inactive
        session and refreshes ``last_active_at``, which the sidebar and
        ``list_subsessions`` use to decide which inactive sessions to show.

        Low-level setter only — it fires no hooks. Deactivation goes through
        :meth:`request_end` (the ``session_end`` task), which is where
        ``session_end`` hooks attach. Pausing is not deactivation; activation
        fires nothing.
        """
        from django.utils import timezone
        now = timezone.now()
        if new_value == self.model.is_active:
            if new_value:
                # Idempotent activation still signals activity: every inbound
                # message path calls this, so the stamp tracks real use.
                self.model.atomic_update(last_active_at=now)
            return

        self.model.atomic_update(is_active=new_value, last_active_at=now)

    def _has_active_call(self) -> bool:
        """Return True if there is any non-ended call for this session.

        Queue/merge admission ("one live turn per session") must account for
        tool and subagent work too, not just ingest/turn calls: a previous
        turn's tool calls (e.g. a still-running ``update_timeline``) keep the
        session busy after their ``process_turn`` already ended, and a new
        message dispatched on top would fire a second LLM query mid-tool-call.
        Parked ``WAITING_QUEUE`` entries count as pending work as well, so a
        new message cannot jump ahead of an older parked one (FIFO).
        """
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.enums.task_enums import TaskCallStatus
        return AgentTaskCall.objects.filter(
            session=self.model,
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
                max_context_tokens = self.auto_compact_max_tokens
            elif (self.auto_compact_max_tokens or 0) > 0:
                max_context_tokens = min(max_context_tokens, self.auto_compact_max_tokens)

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
