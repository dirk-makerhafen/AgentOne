from __future__ import annotations
from django.db import models
from runtime.agents.agent import Agent
from server.models.base_model import BaseModel
from django.core.exceptions import ValidationError

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from server.models.agents.agent_version import AgentVersionModel

class AgentModel(BaseModel):
    """
    Uniquely identifies an Agent across all versions and variants.
    """
    name = models.CharField(max_length=255, unique=True)
    latest_agent_version = models.ForeignKey("server.AgentVersionModel", default=None, null=True, on_delete=models.SET_NULL, related_name='related_newest_version')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills

    @property
    def agent_instances(self):
        return self.related_agent_instances # pyright: ignore[reportAttributeAccessIssue]

    @property
    def agent_versions(self):
        return self.related_agent_versions # pyright: ignore[reportAttributeAccessIssue]

    def get_runtime(self):
        return Agent(agent_model=self)
    
    #@property
    #def latest_agent_version(self) -> AgentVersion:
    #    return self.related_agent_versions.last() # pyright: ignore[reportAttributeAccessIssue]

    #@property
    #def conversation_messages(self):
    #    return self.related_conversation_messages # pyright: ignore[reportAttributeAccessIssue]

    #@property
    #def queries(self):
    #    return self.related_queries # pyright: ignore[reportAttributeAccessIssue]

    #@property
    #def responses(self):
    #    return self.related_responses # pyright: ignore[reportAttributeAccessIssue]

    #@property
    #def tool_calls(self):
    #    return self.related_tool_calls # pyright: ignore[reportAttributeAccessIssue]

    #@property
    #def tool_responses(self):
    #    return self.related_tool_responses # pyright: ignore[reportAttributeAccessIssue]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 

    def __str__(self):
        return self.name
    
