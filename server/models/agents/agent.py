from __future__ import annotations
from django.db import models
from server.models.sessions.session import SessionModel
from server.models.base_model import BaseModel
from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from typing import TYPE_CHECKING, List, Union
from runtime.agents.agent import Agent

if TYPE_CHECKING:
    from server.models.agents.agent_version import AgentVersionModel
    from runtime.agents.agent import Agent

class AgentModel(BaseModel):
    """
    Uniquely identifies an Agent across all versions and variants.
    """
    name = models.CharField(max_length=255, unique=True)
    latest_agent_version = models.ForeignKey("server.AgentVersionModel", default=None, null=True, on_delete=models.SET_NULL, related_name='related_newest_version')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills
    
    parent_skill = models.ForeignKey("server.SkillModel", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
    parent_agent = models.ForeignKey("server.AgentModel", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
    parent_project = models.ForeignKey("server.Project", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills

    @property
    def agent_sessions(self) -> Union[QuerySet, List[SessionModel]]:
        return self.related_agent_sessions # pyright: ignore[reportAttributeAccessIssue]

    @property
    def agent_versions(self) -> Union[QuerySet, List[AgentVersionModel]]:
        return self.related_agent_versions # pyright: ignore[reportAttributeAccessIssue]

    def get_runtime(self) -> Agent:
        return Agent(agent_model=self)
    
    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 

    def __str__(self):
        return self.name
    
