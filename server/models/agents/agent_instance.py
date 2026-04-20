from __future__ import annotations
from django.db import models
from server.models.queries.query import Query
from server.models.queries.response import Response

from server.models.conversation_message import ConversationMessage
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
    created_by   = models.ForeignKey("self", on_delete=models.CASCADE, related_name="created_agent_instances", default=None, null=True, blank=True)

    @property
    def instance_home(self):
        if self.agent and self.agent.pk and self.pk:
            return f"/Users/Dirk/ai/AgentHome/agent:{self.agent.pk}/instance:{self.pk}"

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
        return ConversationMessage.objects.filter(agent_instance_version__agent_instance=self)

    @property
    def queries(self):
        return Query.objects.filter(agent_instance_version__agent_instance=self)

    @property
    def responses(self):
        return Response.objects.filter(agent_instance_version__agent_instance=self)
    
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
