from __future__ import annotations
from typing import List, Any, Dict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.models.agents.agent_instance_version import InstanceVersionModel
    from server.models.agents.agent_instance import InstanceModel

'''
class InstanceModel(BaseModel):
    agent = models.ForeignKey("server.AgentModel", on_delete=models.CASCADE,  related_name="related_agent_instances")
    name  = models.CharField(max_length=255)
    created_by = models.ForeignKey("self", on_delete=models.CASCADE, related_name="created_agent_instances", default=None, null=True, blank=True)
    latest_instance_version = models.ForeignKey("server.InstanceVersionModel", default=None, null=True, on_delete=models.CASCADE, related_name='related_newest_version')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills

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


class ProfileModel(BaseModel):
    aimodel = models.ForeignKey("server.AiModel", on_delete=models.CASCADE, related_name="related_agent_profiles", blank=True, null=True)
    thinking = models.BooleanField(default=True)
   
    max_retries = models.IntegerField(default=0)
    max_task_steps = models.IntegerField(default=0)
    unattended_steps = models.IntegerField(default=0)
    max_history_messages = models.IntegerField(default=0)
    priority = models.IntegerField(default=0)   # 0 = highest, 1..999 less important

    task_prompt   = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="agent_profile_task_prompt")
    system_prompt = models.ForeignKey(GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="agent_profile_system_prompt")

    execution_mode = models.CharField(max_length=20, default=TaskExecutionMode.QUEUE, choices=TaskExecutionMode)
    tool_call_syntax = models.CharField(max_length=20, choices=AgentToolCallSyntax.choices, default=AgentToolCallSyntax.DEFAULT)

    commandNames = models.JSONField(default=list, blank=True)
    disallowedCommandNames = models.JSONField(default=list, blank=True)

    taskNames = models.JSONField(default=list, blank=True)
    disallowedTaskNames = models.JSONField(default=list, blank=True)

    toolNames = models.JSONField(default=list, blank=True)
    disallowedToolNames = models.JSONField(default=list, blank=True)

    skillNames = models.JSONField(default=list, blank=True)
    disallowedSkillNames = models.JSONField(default=list, blank=True)
    
    extra_settings = models.JSONField(default=dict, blank=True, null=True)

'''

class Instance():
    def __init__(self, instance_model: InstanceModel, pinned_instance_version: InstanceVersionModel|None = None):
        self._instance_model = instance_model
        self._pinned_instance_version = pinned_instance_version

    def _get_version(self) -> InstanceVersionModel:
        if self._pinned_instance_version:
            return self._pinned_instance_version 
        return self._instance_model.latest_instance_version

    def _set_version(self, instance_version: InstanceVersionModel):
        self._pinned_instance_version = instance_version

    # FROM INSTANCE
    @property
    def name(self): 
        return self._instance_model.name
    
    # FROM INSTANCE VERSION
    @property
    def description(self): 
        return self._get_version().description
    @property
    def workingdir(self): 
        return self._get_version().workingdir
    @property
    def version_number(self): 
        return self._get_version().version_number
    
    # FROM AGENT PROFILE
    @property
    def max_retries(self) -> int|None:
        return self._resolve_profile_value("max_retries")
    @property
    def max_task_steps(self) -> int|None:
        return self._resolve_profile_value("max_task_steps")
    @property
    def unattended_steps(self) -> int|None:
        return self._resolve_profile_value("unattended_steps")
    @property
    def max_history_messages(self) -> int|None:
        return self._resolve_profile_value("max_history_messages")
    @property
    def priority(self) -> int|None:
        return self._resolve_profile_value("priority")
    @property
    def task_prompt(self) -> str|None:
        return self._resolve_profile_value("task_prompt")
    @property
    def system_prompt(self) -> str|None:
        return self._resolve_profile_value("task_prompt")
    @property
    def execution_mode(self) -> str|None:
        return self._resolve_profile_value("execution_mode")
    @property
    def tool_call_syntax(self) -> str|None:
        return self._resolve_profile_value("tool_call_syntax")
    @property
    def commandNames(self) -> str|None:
        return self._resolve_profile_value("commandNames")
    @property
    def disallowedCommandNames(self) -> str|None:
        return self._resolve_profile_value("disallowedCommandNames")
    @property
    def taskNames(self) -> str|None:
        return self._resolve_profile_value("taskNames")
    @property
    def disallowedTaskNames(self) -> str|None:
        return self._resolve_profile_value("disallowedTaskNames")
    @property
    def toolNames(self) -> str|None:
        return self._resolve_profile_value("toolNames")
    @property
    def disallowedToolNames(self) -> str|None:
        return self._resolve_profile_value("disallowedToolNames")
    @property
    def skillNames(self) -> str|None:
        return self._resolve_profile_value("skillNames")
    @property
    def disallowedSkillNames(self) -> str|None:
        return self._resolve_profile_value("disallowedSkillNames")

    def _resolve_profile_value(self, name:str) -> Any:
        return self._get_version()._resolve_profile_value(name) # ._resolve_profile_value(name)

    

    def all_versions(self):
        pass
