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
from server.models.base_model import BaseModel
from server.models.content import GenericContent
from server.models.enums.task_enums import TaskType
from server.models.settings import SettingsModel
from server.models.skills.skill_version import SkillModelVersion
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.workspace import WorkspaceModel

if TYPE_CHECKING:
    from server.models.sessions.session_version import SessionVersionModel

AGENT_VERSION_RUNTIME_CLASS_CACHE = LRUCache(maxsize=1024)


@contextmanager
def temp_sys_path(path: Path) -> Any:
    """Temporarily adds a directory to sys.path."""
    pathstr = path.as_posix()
    if pathstr not in sys.path:
        sys.path.insert(0, pathstr)
        try:
            yield
        finally:
            sys.path.remove(pathstr)
    else:
        yield


class AgentVersionModel(BaseModel):
    """A versioned snapshot of an agent's configuration."""

    agent = models.ForeignKey(
        "server.AgentModel",
        on_delete=models.CASCADE,
        related_name="related_agent_versions",
    )

    description = models.TextField(max_length=65500, default="")

    extends_agent_names = models.JSONField(default=list, blank=True)
    extends_agent_versions = SortedManyToManyField(
        "self", related_name="related_inheritors", default=None, symmetrical=False
    )

    defined_skill_versions = models.ManyToManyField(
        SkillModelVersion, default=None, related_name="related_agent_versions", symmetrical=False
    )
    defined_task_versions = models.ManyToManyField(
        TaskDefinitionVersion,
        default=None,
        related_name="related_agent_versions",
        symmetrical=False,
    )
    defined_subagent_versions = models.ManyToManyField(
        "self", related_name="related_parents", default=None, symmetrical=False
    )

    skill_versions = models.ManyToManyField(
        SkillModelVersion,
        default=None,
        related_name="used_by_agent_versions",
        symmetrical=False,
        blank=True,
    )
    task_versions = models.ManyToManyField(
        TaskDefinitionVersion,
        default=None,
        related_name="used_by_agent_versions",
        symmetrical=False,
        blank=True,
    )
    subagent_versions = models.ManyToManyField(
        "self",
        default=None,
        related_name="used_by_agent_versions",
        symmetrical=False,
        blank=True,
    )
    subagent_configs = models.JSONField(default=dict, blank=True)

    agent_settings = models.ForeignKey(
        SettingsModel,
        default=None,
        null=True,
        on_delete=models.SET_NULL,
        related_name="related_agent_versions",
    )

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
    ) -> SessionVersionModel:
        """Get or create a session for this agent version.

        Args:
            name: Unique session name. Auto-generated if omitted.
            display_name: Human-readable display name.
            workspace: Workspace directory for the session.
            parent_session_version: Optional parent session version to inherit from.

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

        session, _ = SessionModel.objects.get_or_create(
            name=name,
            defaults=dict(
                parent_session=parent_instance,
            ),
        )
        print("did crete session", session)
        
        session_version:SessionVersionModel = session.latest_session_version
        print("session_version", session_version)
        aiv_created = False
    
        if not session_version or (session_version.pinned_agent_version or session_version.agent.latest_agent_version) != self or session_version.session != session or session_version.workspace != workspace:
            session_version, aiv_created = SessionVersionModel.objects.get_or_create(
                agent=self.agent,
                description=description,
                session=session,
                workspace=workspace,
                display_name=display_name,
                defaults=dict(
                    parent_session_version=parent_session_version,
                ),
            )
        if  aiv_created and session_version:
            session.latest_session_version = session_version
            session.save()

        if parent_session_version:
            parent_session_version.child_session_versions.add(session_version)
        return session_version

    def get_runtime(self) -> Agent:
        """Return a runtime Agent pinned to this version."""
        return Agent(agent_model=self.agent, pinned_agent_version=self)

    def tasks(self) -> QuerySet:
        """Return task versions classified as TASK type."""
        return self.task_versions.filter(task_type=TaskType.TASK)

    def tools(self) -> QuerySet:
        """Return task versions classified as TOOL type."""
        return self.task_versions.filter(task_type=TaskType.TOOL)

    def commands(self) -> QuerySet:
        """Return task versions classified as COMMAND type."""
        return self.task_versions.filter(task_type=TaskType.COMMAND)

    def skills(self):
        """Return all skill versions available to this agent version."""
        return self.skill_versions

    def resolve_setting(self, name: str) -> Any:
        """Resolve a setting value, walking the agent inheritance chain.

        Uses ``*`` (wildcard) elements in list settings to merge parent values.
        """
        extend_at_index = None
        if (value := getattr(self.agent_settings, name)) is not None:
            if isinstance(value, (str, int, bool, GenericContent, BaseModel)):
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

    def resolve_property(self, name: str) -> Any:
        """Resolve a property value, walking the agent inheritance chain."""
        extend_at_index = None
        if (value := getattr(self, name)) is not None:
            if isinstance(value, (str, int, bool, GenericContent)):
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
