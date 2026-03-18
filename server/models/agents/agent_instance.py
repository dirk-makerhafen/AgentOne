from __future__ import annotations
from django.db import models
from server.models.base_model import BaseModel
from django.core.exceptions import ValidationError

from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from server.models.agents.agent_instance_version import AgentInstanceVersion
    from server.models.tasks.agent_task_instance import AgentTaskInstance
    from server.models.agents.agent_version import AgentVersion
    from server.models.agents.agent_profile import AgentProfile

class AgentInstance(BaseModel):
    agent                 = models.ForeignKey("server.Agent"       , on_delete=models.CASCADE,  related_name="related_agent_instances")
    name  = models.CharField(max_length=255)
    parent   = models.ForeignKey("self", on_delete=models.CASCADE, related_name="child_agent_instances", default=None, null=True, blank=True)

    @property
    def tools(self):
        return self.agent_version.tools

    @property
    def agent_version(self) -> "AgentVersion":
        agent_version = self.latest_agent_instance_version.agent_version
        if agent_version:
            return agent_version
        return self.agent.related_agent_versions.last() # pyright: ignore[reportAttributeAccessIssue]

    @property
    def latest_agent_instance_version(self) -> AgentInstanceVersion:
        return self.related_agent_instance_versions.last() # pyright: ignore[reportAttributeAccessIssue]

    @property
    def agent_instance_versions(self) -> list[AgentInstanceVersion]:
        return self.related_agent_instance_versions # pyright: ignore[reportAttributeAccessIssue]

    @property
    def conversation_messages(self):
        return self.related_conversation_messages # pyright: ignore[reportAttributeAccessIssue]

    @property
    def queries(self):
        return self.related_queries # pyright: ignore[reportAttributeAccessIssue]

    @property
    def responses(self):
        return self.related_responses # pyright: ignore[reportAttributeAccessIssue]
    
    @property
    def agent_task_instances(self):
        return self.latest_agent_instance_version.related_agent_task_instances

    @property
    def agent_task_calls(self):
        return self.related_agent_task_calls # pyright: ignore[reportAttributeAccessIssue]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"<Agent#{self.agent.pk}'{self.agent.name}'__AgentInstance#{self.pk}'{self.name}'>"
