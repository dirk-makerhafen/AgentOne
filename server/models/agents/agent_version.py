"""Agent version model — snapshot of an agent's configuration at a point in time."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from cachetools import LRUCache
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import QuerySet
from sortedm2m.fields import SortedManyToManyField

from runtime.agents.agent import Agent
from server.models.base_model import BaseModel, Observables
from server.models.content import GenericContent
from server.models.enums.task_enums import TaskType
from server.models.settings import SettingsModel
from server.models.skills.skill_version import SkillModelVersion
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.workspace import WorkspaceModel

if TYPE_CHECKING:
    from server.models.sessions.session_version import SessionVersionModel


class AgentVisibility(models.TextChoices):
    """Who an agent version is meant for.

    - ``USER``: appears in user pickers (new chat, composer, cron) and is
      spawnable as a subagent. The default.
    - ``SUBAGENT``: hidden from user pickers, but other agents may spawn it
      (planner, researcher, …).
    - ``INTERNAL``: hidden from user pickers *and* from subagent spawning;
      only framework code may instantiate it by name (approval_decider, …).
    - ``MIXIN``: a partial bundle whose params/tasks/tools are inherited by
      extending agents; its visibility never propagates (a mixin is not a
      real agent identity). Hidden from pickers and never spawnable.
    """

    USER = "user", "user"
    SUBAGENT = "subagent", "subagent"
    INTERNAL = "internal", "internal"
    MIXIN = "mixin", "mixin"


DEFAULT_AGENT_VISIBILITY = AgentVisibility.USER.value



class AgentVersionModel(BaseModel):
    """A versioned snapshot of an agent's configuration."""

    class AgentVersionModelObservables(Observables):
        """Explicit observable keys for an AgentVersionModel (IDE autocomplete)."""
        @property
        def pinned_sessions(self):
            return f"SessionVersionModel.pinned_agent_version:{self.model.pk}"

    agent = models.ForeignKey("server.AgentModel",on_delete=models.CASCADE,related_name="related_agent_versions")

    description = models.TextField(max_length=65500, default="")

    # Undeclared (NULL) means "inherit through extends, else user".
    # Stored per version so changing it bumps the agent version.
    visibility = models.CharField(
        max_length=16,
        choices=AgentVisibility.choices,
        default=None,
        null=True,
    )

    extends_agent_names = models.JSONField(default=list, blank=True)
    extends_agent_versions = SortedManyToManyField("self", related_name="related_inheritors", default=None, symmetrical=False)

    defined_skill_versions = models.ManyToManyField(SkillModelVersion, default=None, related_name="related_agent_versions", symmetrical=False)
    defined_task_versions = models.ManyToManyField(TaskDefinitionVersion,default=None,related_name="related_agent_versions",symmetrical=False)
    defined_subagent_versions = models.ManyToManyField("self", related_name="related_parents", default=None, symmetrical=False)

    skill_versions = models.ManyToManyField(SkillModelVersion,default=None,related_name="used_by_agent_versions",symmetrical=False,blank=True)
    task_versions = models.ManyToManyField(TaskDefinitionVersion,default=None,related_name="used_by_agent_versions",symmetrical=False,blank=True)
    subagent_versions = models.ManyToManyField("self",default=None,related_name="used_by_agent_versions",symmetrical=False,blank=True)
    subagent_configs = models.JSONField(default=dict, blank=True)

    #: Session-hook entries from ``agent.md`` (``hooks:`` list of dicts:
    #: on/matcher/agent/task/ingest/max_tokens/timeout_seconds — see
    #: ``docs/session-hooks.md`` §7). Own entries only; the extends-chain
    #: merge happens at runtime (``Agent.hooks``). Same pattern as
    #: ``subagent_configs``: set on create, not part of version identity.
    hooks = models.JSONField(default=list, blank=True)

    agent_settings = models.ForeignKey(SettingsModel,default=None,null=True,on_delete=models.SET_NULL,related_name="related_agent_versions")

    version_number = models.IntegerField(default=0)
    commit = models.CharField(max_length=1024, default="")
    hash = models.CharField(max_length=1024, default="")

    class Meta:
        unique_together = ("agent", "version_number")

    def get_or_create_session(
        self,
        name: Optional[str] = None,
        description: Optional[str] = "",
        display_name: Optional[str] = None,
        workspace: Optional[WorkspaceModel] = None,
        parent_session_version: SessionVersionModel | None = None,
        session_type: str = "",
        settings_inherit: bool = False,
        settings: Optional["SettingsModel"] = None,
        settings_overrides: Optional[dict] = None,
        inherit_links: bool = False,
    ) -> SessionVersionModel:
        """Get or create a session for this agent version.

        Args:
            name: Unique session name. Auto-generated if omitted.
            display_name: Human-readable display name.
            workspace: Workspace directory for the session.
            parent_session_version: Optional parent session version to inherit from.
            session_type: SessionType value describing the session's purpose
                (e.g. "session", "subsession", "subtask_delegate"). Empty
                keeps the SessionModel default.
            settings_inherit: When ``True`` and the parent has session settings,
                clone them onto the child (with ``settings_overrides`` applied
                on top). Same-agent forks only — a different-agent child must
                not shadow its own agent settings with the parent's.
            settings: An explicit, fully-formed settings row to attach. Takes
                precedence over inheritance/overrides.
            settings_overrides: Field overrides applied on top of the inherited
                parent settings, or on top of a blank row when not inheriting.
            inherit_links: When ``True``, copy the parent's query-template and
                adhoc-tool links (copy-on-write). Same-agent forks only.

        Returns:
            The existing or newly created SessionVersionModel.
        """
        from server.models.sessions.session import SessionModel
        from server.models.sessions.session_version import SessionVersionModel

        if not workspace and parent_session_version:
            workspace = parent_session_version.workspace
        parent_instance = parent_session_version.session if parent_session_version else None
        if not name:
            name = f"p{parent_instance.pk}:{self.agent.name}" if parent_instance else f"default:{self.agent.name}"

        if not display_name:
            display_name = f"{self.agent.name}"

        # Resolve the child's settings *before* creating the version so they can
        # ride along in ``defaults`` — SessionVersionModel is immutable once it
        # has a pk, so a post-create ``.update()`` would be the only alternative.
        child_settings = self._resolve_child_settings(
            parent_session_version, settings_inherit, settings, settings_overrides
        )

        session_defaults = dict(
            parent_session=parent_instance,
        )
        if session_type:
            session_defaults["session_type"] = session_type

        # ``parent_session`` belongs in the *lookup*, not only in ``defaults``.
        # As a default it applied on create alone, so a second caller reusing
        # the name got back the first caller's session — two projects each
        # naming a session "research" shared one row, one turn_count and one
        # message chain.  ``None`` is translated to IS NULL, which also scopes
        # top-level sessions correctly.
        session, _ = SessionModel.objects.get_or_create(
            name=name,
            parent_session=parent_instance,
            defaults=session_defaults,
        )

        session_version:SessionVersionModel = session.latest_session_version
        aiv_created = False
    
        if not session_version or (session_version.pinned_agent_version or session_version.agent.latest_agent_version) != self or session_version.session != session or session_version.workspace != workspace:
            session_version, aiv_created = SessionVersionModel.objects.get_or_create(
                agent=self.agent,
                description=description,
                session=session,
                workspace=workspace,
                display_name=display_name,
                pinned_agent_version=self,
                defaults=dict(
                    parent_session = parent_session_version.session if parent_session_version else None,
                    parent_session_version=parent_session_version,
                    session_settings=child_settings,
                    # Pin new sessions to the creating AgentVersion so later
                    # reload_all runs don't shift system prompt / tool schemas
                    # mid-conversation (KV-cache prefix stability).  Upgrades
                    # happen explicitly after compaction or via the UI banner.
                ),
            )
        if  aiv_created and session_version:
            session.latest_session_version = session_version
            session.save()

        if parent_session_version:
            parent_session_version.child_session_versions.add(session_version)

        # Forks inherit the parent's query-template and adhoc-tool links
        # (copy-on-write: no version rows minted, history shared until the
        # child first saves).  Only for newly created, same-agent forks — a
        # pre-existing session already has its own links.
        if aiv_created and inherit_links and parent_session_version:
            from runtime.query_templates import inherit_templates

            inherit_templates(parent_session_version.session_id, session.pk)
            from runtime.adhoc_tools import inherit_adhoc_tools

            inherit_adhoc_tools(parent_session_version.session_id, session.pk)

        return session_version

    def _resolve_child_settings(
        self,
        parent_session_version: SessionVersionModel | None,
        settings_inherit: bool,
        settings: Optional["SettingsModel"],
        settings_overrides: Optional[dict],
    ) -> Optional["SettingsModel"]:
        """Build the settings row for a newly created child session.

        Precedence: an explicit ``settings`` row wins; otherwise the parent's
        settings are cloned (only when ``settings_inherit``) with overrides on
        top; otherwise a blank row carrying just the overrides.
        """
        if settings is not None:
            return settings
        if settings_inherit and parent_session_version and parent_session_version.session_settings:
            return self.clone_settings(
                parent_session_version.session_settings, **(settings_overrides or {})
            )
        if settings_overrides:
            row = SettingsModel(**settings_overrides)
            row.save()
            return row
        return None

    def get_runtime(self) -> Agent:
        """Return a runtime Agent pinned to this version."""
        return Agent(agent_model=self.agent, pinned_agent_version=self)

    def tasks(self) -> QuerySet:
        """Return task versions classified as TASK type."""
        # Deterministic order: the tools/tasks/commands arrays are rendered
        # into the LLM request, so their order is part of the prefix-cache
        # key.  The M2M join has no inherent order (nondeterministic on
        # MySQL) — sort by definition name so the same tool set always
        # serialises to the same bytes.
        return self.task_versions.filter(task_type=TaskType.TASK).order_by(
            "task_definition__name", "pk"
        )

    def tools(self) -> QuerySet:
        """Return task versions classified as TOOL type."""
        # Deterministic order: see tasks() — prompt prefix stability.
        return self.task_versions.filter(task_type=TaskType.TOOL).order_by(
            "task_definition__name", "pk"
        )

    def commands(self) -> QuerySet:
        """Return task versions classified as COMMAND type."""
        # Deterministic order: see tasks() — prompt prefix stability.
        return self.task_versions.filter(task_type=TaskType.COMMAND).order_by(
            "task_definition__name", "pk"
        )

    def skills(self):
        """Return all skill versions available to this agent version."""
        return self.skill_versions

    def resolve_setting(self, name: str) -> Any:
        """Resolve a setting value, walking the agent inheritance chain.

        Uses ``*`` (wildcard) elements in list settings to merge parent values.
        """
        extend_at_index = None
        if (value := getattr(self.agent_settings, name)) is not None:
            if isinstance(value, (str, int, bool, float, GenericContent, BaseModel)):
                return value
            if isinstance(value, dict):
                return value
            if isinstance(value, (list,)):
                if "+" not in value:
                    return value
                extend_at_index = value.index("+")
            else:
                raise Exception(
                    f"_get_agent_setting does not yet support type of '{name}': {type(value)}"
                )
        for extends_agent_version in self.extends_agent_versions.all():
            if (ext_value := extends_agent_version.resolve_setting(name)) is not None:
                if isinstance(value, (list,)) and extend_at_index is not None:
                    value[extend_at_index : extend_at_index + 1] = ext_value
                else:
                    return ext_value
        return value


    def clone_settings(self, settings: "SettingsModel", **overrides: Any) -> "SettingsModel":
        """Create a fresh immutable SettingsModel row copying *settings'* fields.

        ``SettingsModel`` instances are immutable (``save`` raises once a pk is
        set), so forks can not share the parent's exact row — a fork must get its
        own snapshot row with the same field values.  ``overrides`` are applied
        on top (e.g. ``auto_compact_max_tokens=0`` to stop a fork from re-forking).
        """
        clone = SettingsModel()
        for field in SettingsModel._meta.fields:
            name = field.name
            if name in ("id", "created_at", "updated_at"):
                continue
            if getattr(field, "auto_created", False):
                continue
            try:
                setattr(clone, field.attname, getattr(settings, field.attname))
            except Exception:  # pylint: disable=broad-exception-caught
                continue
        for name, value in overrides.items():
            setattr(clone, name, value)
        clone.save()
        return clone


    def collect_system_prompts(self) -> list[str]:
        """Collect all system prompts from this agent and its ancestors.

        Returns a list of system prompts in inheritance order (parent first,
        then child), excluding empty prompts. This allows child agents to
        inherit and extend parent system prompts when inheritSystemPrompt
        is enabled.

        The inheritSystemPrompt flag on THIS agent controls whether parent
        prompts are included. If false, only this agent's own prompt is returned.
        """
        prompts: list[str] = []

        # Check if THIS agent inherits parent system prompts
        if getattr(self.agent_settings, "inherit_system_prompt", False):
            # Walk the extends chain recursively (parent first)
            for extends_agent_version in self.extends_agent_versions.all():
                prompts.extend(extends_agent_version.collect_system_prompts())

        # Add this agent's own system prompt (if non-empty)
        sp = getattr(self.agent_settings, "system_prompt", None)
        if sp:
            if isinstance(sp, GenericContent):
                text = sp.get()
            else:
                text = str(sp)
            text = text.strip()
            if text:
                prompts.append(text)

        return prompts

    def resolve_property(self, name: str) -> Any:
        """Resolve a property value, walking the agent inheritance chain."""
        extend_at_index = None
        if (value := getattr(self, name)) is not None:
            if isinstance(value, (str, int, bool, float, GenericContent)):
                return value
            if isinstance(value, (list,)):
                if "+" not in value:
                    return value
                extend_at_index = value.index("+")
            else:
                raise Exception(
                    f"resolve_property does not yet support type of '{name}': {type(value)}"
                )
        for extends_agent_version in self.extends_agent_versions.all():
            # Mixin agents are partial bundles: their visibility must not
            # propagate to inheritors (a mixin is not a real agent identity).
            if name == "visibility" and getattr(
                extends_agent_version, "visibility", None
            ) == "mixin":
                continue
            if (ext_value := extends_agent_version.resolve_property(name)) is not None:
                if isinstance(value, (list,)) and extend_at_index is not None:
                    value[extend_at_index : extend_at_index + 1] = ext_value
                else:
                    return ext_value
        return value

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Prevent updates to existing AgentVersionModel instances."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.agent.name} v{self.version_number}"
