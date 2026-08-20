from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import QuerySet

from runtime.agents.agent import Agent
from server.models.base_model import BaseModel, Observables


class AgentModel(BaseModel):
    """Uniquely identifies an Agent across all versions and variants."""

    class AgentModelObservables(Observables):
        """Explicit observable keys for an AgentModel (IDE autocomplete)."""
        @property
        def child_agents(self):
            return f"AgentModel.parent_agent:{self.model.pk}"
        @property
        def child_skills(self):
            return f"SkillModel.parent_agent:{self.model.pk}"
        @property
        def cron_jobs(self):
            return f"Cronjob.agent:{self.model.pk}"

    name = models.CharField(max_length=255, unique=True)
    latest_agent_version = models.ForeignKey("server.AgentVersionModel",default=None,null=True,on_delete=models.SET_NULL,related_name="related_newest_version")
    parent_skill = models.ForeignKey("server.SkillModel",default=None,null=True, blank=True, on_delete=models.CASCADE,related_name="child_agents")
    parent_agent = models.ForeignKey("server.AgentModel",default=None,null=True, blank=True, on_delete=models.CASCADE,related_name="child_agents")
    parent_project = models.ForeignKey("server.Project",default=None,null=True, blank=True, on_delete=models.CASCADE,related_name="child_agents")

    @property
    def agent_sessions(self) -> QuerySet:
        """Return related session versions for this agent."""
        return self.related_agent_sessions  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def agent_versions(self) -> QuerySet:
        """Return related agent version instances."""
        return self.related_agent_versions  # pyright: ignore[reportAttributeAccessIssue]

    def get_runtime(self) -> Agent:
        """Return a runtime Agent wrapper for this model."""
        return Agent(agent_model=self)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Prevent updates to existing AgentModel instances."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name
