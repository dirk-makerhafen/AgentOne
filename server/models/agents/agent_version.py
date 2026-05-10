from __future__ import annotations

from contextlib import contextmanager
import sys
from typing import Any, Dict, Optional, Type
from cachetools import LRUCache
from django.db import models
from django.core.exceptions import ValidationError

from runtime.agents.agent import Agent
from server.models.agents.agent import AgentModel
from server.models.agents.profile import ProfileModel
from server.models.base_model import BaseModel
from server.models.content import GenericContent
from pathlib import Path

from typing import TYPE_CHECKING
from sortedm2m.fields import SortedManyToManyField

from server.models.enums.task_enums import TaskType
from server.models.tasks.task_definition import TaskDefinition
if TYPE_CHECKING:
    from server.models.agents.agent_instance_version import InstanceVersionModel

AGENT_VERSION_RUNTIME_CLASS_CACHE = LRUCache(maxsize=1024)

@contextmanager
def temp_sys_path(path:Path):
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
    """
    A versioned snapshot of an agent 
    """    
    parent_skill = models.ForeignKey("server.Skill", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
    parent_agent = models.ForeignKey("server.AgentModel", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
    parent_project = models.ForeignKey("server.Project", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills
    
    agent = models.ForeignKey("server.AgentModel"        , on_delete=models.CASCADE, related_name="related_agent_versions")

    description = models.TextField(max_length=65500, default="")

    extendsAgents = SortedManyToManyField("server.AgentModel", related_name="related_inheritors", default=None, null=True)
    extendsAgentVersions = SortedManyToManyField("server.AgentVersionModel", related_name="related_inheritors", default=None, null=True)

    extendsAgentNames = models.JSONField(default=list, blank=True)

    agent_profile = models.ForeignKey(ProfileModel ,default=None,null=True, on_delete=models.SET_NULL, related_name="related_agent_versions") # top level profile

    version_number = models.IntegerField(default=0)
    commit = models.TextField(max_length=1024, default="")

    class Meta:
        unique_together = ("agent", "version_number")


    '''

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
    #def agent_instance_versions(self):
    #    return self.related_agent_instance_versions # pyright: ignore[reportAttributeAccessIssue]

    #@property
    #def agent_task_calls(self):
    #    return self.related_agent_task_calls # pyright: ignore[reportAttributeAccessIssue]

    def get_or_create_instance(self, name:Optional[str] = None, display_name:Optional[str]=None, workingdir: Optional[str|Path] = None, parent_instance_version:InstanceVersionModel|None=None) -> InstanceVersionModel:
        from server.models.agents.agent_instance import InstanceModel
        from server.models.agents.agent_instance_version import InstanceVersionModel
        if not workingdir and parent_instance_version:
            workingdir = parent_instance_version.workingdir
        if workingdir:
            workingdir = Path(workingdir).resolve()
        parent_instance = parent_instance_version.agent_instance if parent_instance_version else None
        if not name:
            if "FunctionSummaryAgent" in self.agent.name:
                raise Exception(f"faiked {self.agent}")
            name = f"p{parent_instance.pk}:{self.agent.name}" if parent_instance else f"default:{self.agent.name}"

        if not display_name:
            display_name = f"{self.agent.name}"

        agent_instance, _ = InstanceModel.objects.get_or_create(
            name = name,
            agent = self.agent,
            defaults = dict(
                created_by = parent_instance,
            )
        )
        agent_instance_version = agent_instance.latest_instance_version
        aiv_created = False
        if not agent_instance_version \
            or agent_instance_version.agent_version != self \
            or agent_instance_version.agent_instance != agent_instance \
            or agent_instance_version.workingdir != workingdir:
                agent_instance_version, aiv_created = InstanceVersionModel.objects.get_or_create(
                    agent = self.agent,
                    agent_version = self,
                    agent_instance = agent_instance,
                    workingdir = workingdir,
                    display_name = display_name,
                    defaults = dict(
                        created_by = parent_instance_version,
                    )
                )
        if aiv_created:
            InstanceModel.objects.filter(pk=agent_instance.pk).update(latest_instance_version=agent_instance_version)
            
        if parent_instance_version:
            parent_instance_version.child_agent_instance_versions.add(agent_instance_version)
        return agent_instance_version

    def get_runtime(self):
        return Agent(agent_model=self.agent, pinned_agent_version=self)
    
    def collect_names(self, agent_version, task_type, taskNames, disallowedTaskNames):
        extends = agent_version.profile.extendsAgents.all()
        print("collect_names", agent_version, extends )
        for extend in extends:
            self.collect_names(extend.latest_agent_version, task_type, taskNames, disallowedTaskNames)
        [taskNames.add(x) for x in agent_version.profile.taskNames]
        [disallowedTaskNames.add(x) for x in agent_version.profile.disallowedTaskNames]   

    def tasks(self):
        '''
        TaskDefinition.parent_skill = models.ForeignKey("server.Skill", default=None, null=True, on_delete=models.CASCADE, related_name='related_task_definitions')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
        TaskDefinition.parent_agent = models.ForeignKey("server.AgentModel", default=None, null=True, on_delete=models.CASCADE, related_name='related_task_definitions')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
        TaskDefinition.parent_project = models.ForeignKey("server.Project", default=None, null=True, on_delete=models.CASCADE, related_name='related_task_definitions')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills
        profile.commandNames = models.JSONField(default=list, blank=True)
        profile.disallowedCommandNames = models.JSONField(default=list, blank=True)
        profile.taskNames = models.JSONField(default=list, blank=True)
        profile.disallowedTaskNames = models.JSONField(default=list, blank=True)
        profile.toolNames = models.JSONField(default=list, blank=True)
        profile.disallowedToolNames = models.JSONField(default=list, blank=True)
        profile.skillNames = models.JSONField(default=list, blank=True)
        profile.disallowedSkillNames = models.JSONField(default=list, blank=True)
        '''
    
        taskNames = set()
        disallowedTaskNames = set()
        self.collect_names(self, TaskType.TASK, taskNames, disallowedTaskNames)
        allowed_task_names = taskNames - disallowedTaskNames
        print("allowed_task_names", allowed_task_names)
        tasks = {}
        def resolve_task(agent_version, task_name):
            task = TaskDefinition.objects.filter(name=task_name, parent_agent = agent_version.agent).first()
            if task:
                tasks[task_name] = task
                return
            extends = agent_version.profile.extendsAgents.all()
            for extend in extends:
                agent = AgentModel.objects.get(name=extend)
                agent_version = agent.latest_agent_version
                resolve_task(agent_version, task_name )
        for allowed_task_name in allowed_task_names:
            resolve_task(self, allowed_task_name)
        print("TASKS TASKS", tasks)

        return TaskDefinition.objects.filter(pk__in=[ v.pk for k, v in tasks.items()])

    def tools(self):
        tools = {}
        def collect_tools(agent_version):
            for extendsAgendName in agent_version.profile.extendsAgentNames:
                extendsAgend = AgentModel.objects.get(name=extendsAgendName)
                collect_tools(extendsAgend.latest_agent_version)
            agentTools = TaskDefinition.objects.filter(task_type=TaskType.TOOL, name__in=agent_version.profile.toolNames).exclude(name__in=agent_version.profile.disallowedToolNames)
            for agentTool in agentTools:
                if agentTool.name in agent_version.profile.disallowedToolNames:
                    continue
                tools[agentTool.name] = agentTool
            for disallowedToolName in agent_version.profile.disallowedToolNames:
                if disallowedToolName in tools:
                    del tools[disallowedToolName]
        collect_tools(self)
        return TaskDefinition.objects.filter(pk__in=[ v.pk for k, v in tools.items()])
        
    def commands(self):
        commands = {}
        def collect_commands(agent_version):
            print("collect_commands", agent_version)
            for extendsAgendName in agent_version.profile.extendsAgentNames:
                print("extendsAgendName", extendsAgendName)
                extendsAgend = AgentModel.objects.get(name=extendsAgendName)
                collect_commands(extendsAgend.latest_agent_version)
            agentCommands = TaskDefinition.objects.filter(task_type=TaskType.COMMAND, name__in=agent_version.profile.commandNames).exclude(name__in=agent_version.profile.disallowedCommandNames)
            for agentCommand in agentCommands:
                if agentCommand.name in agent_version.profile.disallowedCommandNames:
                    continue
                commands[agentCommand.name] = agentCommand
            for disallowedCommandName in agent_version.profile.disallowedCommandNames:
                if disallowedCommandName in commands:
                    del commands[disallowedCommandName]
            print("commands", commands)
        collect_commands(self)
        return TaskDefinition.objects.filter(pk__in=[ v.pk for k, v in commands.items()])

    def skills(self):
        skills = {}
        def collect_skills(agent_version):
            for extendsAgendName in agent_version.profile.extendsAgentNames:
                extendsAgend = AgentModel.objects.get(name=extendsAgendName)
                collect_skills(extendsAgend.latest_agent_version)
            agentSkills = TaskDefinition.objects.filter(task_type=TaskType.TASK, name__in=agent_version.profile.skillNames).exclude(name__in=agent_version.profile.disallowedSkillNames)
            for agentSkill in agentSkills:
                if agentSkill.name in agent_version.profile.disallowedSkillNames:
                    continue
                skills[agentSkill.name] = agentSkill
            for disallowedSkillName in agent_version.profile.disallowedSkillNames:
                if disallowedSkillName in skills:
                    del skills[disallowedSkillName]
        collect_skills(self)
        return TaskDefinition.objects.filter(pk__in=[ v.pk for k, v in skills.items()])
    
    def _resolve_profile_value(self, name) -> Any:
        # check inherited values if our is not set
        if not self.agent_profile:
            return None
        
        extend_at_index = None
        if value := getattr(self.agent_profile, name) is not None:
            if isinstance(value, (str, int, bool, GenericContent)):
                return value
            if isinstance(value, (list,)):
                if "*" not in value: # overwrite parent list 
                    return value
                extend_at_index = value.index("*")
            else:
                raise Exception(f"_resolve_profile_value does not yet support type of '{name}': {type(value)}")
            
        for extendsAgentVersion in self.extendsAgentVersions.all():
            if ext_value := extendsAgentVersion._resolve_profile_value(name) is not None:
                if isinstance(value, (list,)) and extend_at_index is not None:
                    value[extend_at_index:extend_at_index+1] = ext_value
                else:
                    return ext_value
        return value
        
    def _resolve_agent_value(self, name:str) -> Any:
        # check inherited values if our is not set
        
        extend_at_index = None
        if value := getattr(self, name) is not None:
            if isinstance(value, (str,int,bool, GenericContent)):
                return value
            if isinstance(value, (list,)):
                if "*" not in value: # overwrite parent list 
                    return value
                extend_at_index = value.index("*")
            else:
                raise Exception(f"_resolve_agent_value does not yet support type of '{name}': {type(value)}")
        for extendsAgentVersion in self.extendsAgentVersions.all():
            if ext_value := extendsAgentVersion._resolve_agent_value(name) is not None:
                if isinstance(value, (list,)) and extend_at_index is not None:
                    value[extend_at_index:extend_at_index+1] = ext_value
                else:
                    return ext_value
        return value
       

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs) 

    def __str__(self):
        return f"{self.agent.name} v{self.version_number}"

'''
class AgentVersionSubAgentRelation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    parent_agent_version = models.ForeignKey("server.AgentVersionModel", related_name="subagent_relations", on_delete=models.CASCADE)
    sub_agent_version  = models.ForeignKey(AgentVersionModel, related_name="parent_agent_relations", on_delete=models.CASCADE)
    create_option  = models.CharField(max_length=255)
    visible_to  = models.CharField(max_length=255)
    instance_name = models.CharField(max_length=255)
'''
