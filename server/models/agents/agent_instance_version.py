import random
from django.db import models
from server.models.agents.agent_profile import AgentProfile
from server.models.agents.agent_version import AgentVersion
from server.models.agents.agent_instance import AgentInstance
from server.models.agents.agent import Agent

from server.models.base_model import BaseModel
from cachetools import LRUCache
from django.db import models
from django.core.exceptions import ValidationError
from typing import TYPE_CHECKING

AGENT_INSTANCE_VERSION_RUNTIME_CLASS_INSTANCE_CACHE = LRUCache(maxsize=1024)

class AgentInstanceVersion(BaseModel):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="related_agent_instance_versions")
    agent_instance = models.ForeignKey(AgentInstance, on_delete=models.CASCADE, related_name="related_agent_instance_versions")
    agent_version  = models.ForeignKey(AgentVersion,  on_delete=models.CASCADE, related_name="related_agent_instance_versions")
    created_by   = models.ForeignKey("self", on_delete=models.CASCADE, related_name="created_agent_instance_versions", default=None, null=True, blank=True)

    # Instance specific settings
    display_name = models.CharField(max_length=2048, default=None, blank=True, null=True)
    workingdir   = models.CharField(max_length=1024, default=None, blank=True, null=True)
    pinned_agent_profile  = models.ForeignKey(AgentProfile,  on_delete=models.SET_DEFAULT, related_name="related_agent_instance_versions", null=True, blank=True, default=None) # optional pin a profile, otherwise a random profile is selected when this verion is used
    child_agent_instance_versions   = models.ManyToManyField("self", related_name="parent_agent_instance_versions", default=None, null=True, blank=True, symmetrical=False)


    @property
    def agent_task_instances(self):
        return self.related_agent_task_instances # pyright: ignore[reportAttributeAccessIssue]

    @property
    def agent_task_calls(self):
        return self.related_agent_task_calls # pyright: ignore[reportAttributeAccessIssue]

    def select_profile(self, variant_names=None) -> AgentProfile:
        if not variant_names:
            variant_names=[]
        self.pinned_agent_profile: AgentProfile
        if self.pinned_agent_profile:
            return self.pinned_agent_profile.select(variant_names)
        return self.agent_version.profile.select(variant_names)
                            
    def get_runtime_instance(self):
        if not self.pk:
            raise Exception("Cant create runtime instance, save AgentInstanceVersion model first")
        self.agent_version: AgentVersion
        runtime_class = self.agent_version.get_runtime_class()
        print("runtime_class", runtime_class)
        print("agent_instance_version", self)
        runtime_instance = runtime_class(agent_instance_version=self)
        #AGENT_INSTANCE_VERSION_RUNTIME_CLASS_INSTANCE_CACHE[self.pk] = runtime_instance
        print("get_runtime_instance", runtime_instance)
        return runtime_instance
    
    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"<AgentInstance#{self.agent_instance.pk}'{self.agent_instance.name}'__AgentInstanceVersion#{self.pk}>"
