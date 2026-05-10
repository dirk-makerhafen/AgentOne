from django.db import models
from runtime.agents.instance import Instance
from server.models.agents.profile import ProfileModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.agents.agent_instance import InstanceModel
from server.models.agents.agent import AgentModel

from server.models.base_model import BaseModel
from cachetools import LRUCache
from django.db import models
from django.core.exceptions import ValidationError
from typing import TYPE_CHECKING, Any

from server.models.content import GenericContent

AGENT_INSTANCE_VERSION_RUNTIME_CLASS_INSTANCE_CACHE = LRUCache(maxsize=1024)

class InstanceVersionModel(BaseModel):
    agent = models.ForeignKey(AgentModel, on_delete=models.CASCADE, related_name="related_agent_instance_versions")
    agent_instance = models.ForeignKey(InstanceModel, on_delete=models.CASCADE, related_name="related_agent_instance_versions")
    agent_version  = models.ForeignKey(AgentVersionModel,  on_delete=models.CASCADE, related_name="related_agent_instance_versions")

    created_by = models.ForeignKey("self", on_delete=models.CASCADE, related_name="created_agent_instance_versions", default=None, null=True, blank=True)

    name = models.CharField(max_length=255, default="")
    display_name = models.CharField(max_length=2048, default=None, blank=True, null=True)
    description  = models.TextField(max_length=65500, default="")

    workingdir = models.CharField(max_length=1024, default=None, blank=True, null=True)
    child_agent_instance_versions = models.ManyToManyField("self", related_name="parent_agent_instance_versions", default=None, null=True, blank=True, symmetrical=False)

    instance_profile = models.ForeignKey("server.ProfileModel" , on_delete=models.SET_NULL, default=None, null=True, related_name="related_instance_versions") # top level profile

    version_number = models.IntegerField(default=0)
    commit = models.TextField(max_length=1024, default="")

    #@property
    #def agent_task_instances(self):
    #    return self.related_agent_task_instances # pyright: ignore[reportAttributeAccessIssue]

    #@property
    #def agent_task_calls(self):
    #    return self.related_agent_task_calls # pyright: ignore[reportAttributeAccessIssue]

    def _resolve_profile_value(self, name) -> Any:
        agent_profile_value = self.agent_version._resolve_profile_value(name)
        if not self.instance_profile:  # we overwrite nothing, use agents profile
            return agent_profile_value
        
        # we might overwrite agent profile values
        instance_profile_value = getattr(self.instance_profile, name)
        if instance_profile_value is None: # we dont..
            return agent_profile_value 

        if isinstance(instance_profile_value, (str, int, bool, GenericContent)):
            return instance_profile_value
        if isinstance(instance_profile_value, (list,)):
            if "*" not in instance_profile_value: # overwrite parent list 
                return instance_profile_value
            extend_at_index = instance_profile_value.index("*")
            instance_profile_value[extend_at_index:extend_at_index+1] = agent_profile_value
        else:
            raise Exception(f"_resolve_profile_value does not yet support type of '{name}': {type(instance_profile_value)}")
        
        return instance_profile_value

    def get_runtime(self):
        return Instance(instance_model=self.agent_instance, pinned_instance_version=self)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"<AgentInstance#{self.agent_instance.pk}'{self.agent_instance.name}'__AgentInstanceVersion#{self.pk}>"
