from __future__ import annotations
from typing import List, Any, Dict, Union
import ast
from runtime.agents.bound_task import BoundTask
from runtime.agents.session import Session

from server.models.base_model import BaseModel
from server.models.enums.task_enums import TaskType
from server.models.sessions.session import SessionModel
from server.models.content import GenericContent
from server.models.message import Message
from typing import TYPE_CHECKING
from django.db.models import QuerySet

from server.models.tasks.task_definition import TaskDefinition
from server.models.workspace import WorkspaceModel

if TYPE_CHECKING:
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.agents.agent import AgentModel

from server.models.project import Project
from server.models.skills.skill import SkillModel


class Agent():
    def __init__(self, agent_model:AgentModel, pinned_agent_version: AgentVersionModel|None = None ):
        self.model:AgentModel = agent_model
        self._pinned_agent_version = pinned_agent_version
    
    # FROM AGENT
    @property
    def name(self): 
        return self.model.name
    
    @property
    def extends_agent_versions(self):
        return [Agent(agent_model=x.agent, pinned_agent_version=x) for x in self.get_version_model().extends_agent_versions.all()]

    # FROM AGENT VERSION
    @property
    def description(self): 
        return self._get_agent_property("description")
    @property
    def version_number(self): 
        return self.get_version_model().version_number
    
    # FROM AGENT PROFILE
    @property
    def aimodel(self) -> int|None:
        return self._get_agent_setting("aimodel")
    @property
    def max_retries(self) -> int|None:
        return self._get_agent_setting("max_retries")
    @property
    def max_turns(self) -> int|None:
        return self._get_agent_setting("max_turns")
    @property
    def max_unattended_turns(self) -> int|None:
        return self._get_agent_setting("max_unattended_turns")
    @property
    def max_history_messages(self) -> int|None:
        return self._get_agent_setting("max_history_messages")
    @property
    def priority(self) -> int|None:
        return self._get_agent_setting("priority")
    

    @property
    def task_prompt(self) -> str:
        tp = self._get_agent_setting("task_prompt")
        if tp and isinstance(tp, GenericContent):
            return tp.get()
        return tp
       
    @property
    def system_prompt(self) -> str:
        sp = self._get_agent_setting("system_prompt")
        if sp and isinstance(sp, GenericContent):
            return sp.get()
        return sp
    
    @property
    def execution_mode(self) -> str|None:
        return self._get_agent_setting("execution_mode")
    @property
    def tool_call_syntax(self) -> str|None:
        return self._get_agent_setting("tool_call_syntax")
    

    @property
    def definedCommandVersions(self):
        return self.get_version_model().defined_task_versions.filter(task_definition__task_type=TaskType.COMMAND)
    @property
    def commandNames(self) -> list[str]:
        return self._get_agent_setting("commandNames") or []
    @property
    def disallowedCommandNames(self) -> list[str]:
        return self._get_agent_setting("disallowedCommandNames") or []
    @property
    def allowedCommandNames(self) -> list[str]:
        return list(set(self.commandNames) - set(self.disallowedCommandNames))
    @property
    def allowedCommands(self) -> list[TaskDefinition]:
        allowed_commands = []
        for allowedCommandName in self.allowedCommandNames:
            allowed_command = self.get_allowed_command(allowedCommandName)
            if allowed_command:
                allowed_commands.append(allowed_command)
        
        return allowed_commands
    def get_allowed_command(self, name):
        if name not in self.allowedCommandNames:
            print(f"name {name} not in allowed commands")
            return
        command = self.definedCommandVersions.filter(task_definition__name=name).first()
        if command:
            return command
        if self.model.parent_project:
            command = TaskDefinition.objects.filter(parent_project=self.model.parent_project, parent_agent=None, task_type=TaskType.COMMAND, name=name).first()
            if command:
                return command.latest_task_version
        for extends_agent in self.extends_agent_versions:
            command = extends_agent.get_allowed_command(name)
            if command:
                return command
        command = TaskDefinition.objects.filter(parent_project=None, parent_agent=None, task_type=TaskType.COMMAND, name=name).first()
        if command:
            return command.latest_task_version

    @property
    def definedTaskVersions(self):
        return self.get_version_model().defined_task_versions.filter(task_definition__task_type=TaskType.TASK)
    @property
    def taskNames(self) -> list[str]:
        return self._get_agent_setting("taskNames") or []
    @property
    def disallowedTaskNames(self) -> list[str]:
        return self._get_agent_setting("disallowedTaskNames") or []
    @property
    def allowedTaskNames(self) -> list[str]:
        return list(set(self.taskNames) - set(self.disallowedTaskNames))
    @property
    def allowedTasks(self) -> list[TaskDefinition]:
        allowed_tasks = []
        for allowedTaskName in self.allowedTaskNames:
            allowed_task = self.get_allowed_task(allowedTaskName)
            if allowed_task:
                allowed_tasks.append(allowed_task)
        return allowed_tasks
    def get_allowed_task(self, name):
        if name not in self.allowedTaskNames:
            print(f"name {name} not in allowed tasks")
            return
        task = self.definedTaskVersions.filter(task_definition__name=name).first()
        if task:
            return task
        if self.model.parent_project:
            task = TaskDefinition.objects.filter(parent_project=self.model.parent_project, parent_agent=None, task_type=TaskType.TASK, name=name).first()
            if task:
                return task.latest_task_version
        for extends_agent in self.extends_agent_versions:
            task = extends_agent.get_allowed_task(name)
            if task:
                return task
        task = TaskDefinition.objects.filter(parent_project=None, parent_agent=None, task_type=TaskType.TASK, name=name).first()
        if task:
            return task.latest_task_version
    

    @property
    def definedToolVersions(self):
        return self.get_version_model().defined_task_versions.filter(task_definition__task_type=TaskType.TOOL)
    @property
    def toolNames(self) -> list[str]:
        return self._get_agent_setting("toolNames") or []
    @property
    def disallowedToolNames(self) -> list[str]:
        return self._get_agent_setting("disallowedToolNames") or []
    @property
    def allowedToolNames(self) -> list[str]:
        return list(set(self.toolNames) - set(self.disallowedToolNames))
    @property
    def allowedTools(self) -> list[TaskDefinition]:
        allowed_tools = []
        for allowedToolName in self.allowedToolNames:
            allowed_tool = self.get_allowed_tool(allowedToolName)
            if allowed_tool:
                allowed_tools.append(allowed_tool)
        return allowed_tools
    def get_allowed_tool(self, name):
        print("get_allowed_tool", name)
        if name not in self.allowedToolNames:
            print(f"name {name} not in allowed tools")
            return
        tool = self.definedToolVersions.filter(task_definition__name=name).first()
        if tool:
            return tool
        if self.model.parent_project:
            tool = TaskDefinition.objects.filter(parent_project=self.model.parent_project, parent_agent=None, task_type=TaskType.TOOL, name=name).first()
            if tool:
                return tool.latest_task_version
        for extends_agent in self.extends_agent_versions:
            tool = extends_agent.get_allowed_tool(name)
            if tool:
                return tool
        tool = TaskDefinition.objects.filter(parent_project=None, parent_agent=None, task_type=TaskType.TOOL, name=name).first()
        if tool:
            return tool.latest_task_version


    @property
    def definedSkillVersions(self):
        return self.get_version_model().defined_skill_versions.all()
    @property
    def skillNames(self) -> list[str]:
        return self._get_agent_setting("skillNames") or []
    @property
    def disallowedSkillNames(self) -> list[str]:
        return self._get_agent_setting("disallowedSkillNames") or []
    @property
    def allowedSkillNames(self) -> list[str]:
        return list(set(self.skillNames) - set(self.disallowedSkillNames))


    @property
    def definedSubagentVersions(self):
        return self.get_version_model().defined_subagent_versions.all()


    def _get_agent_setting(self, name) -> Any:
        # check inherited values if our is not set
        agent_version_model = self.get_version_model()
        agent_settings = agent_version_model.agent_settings
        if not agent_settings:
            return None
        
        extend_at_index = None
        print("agent1", agent_version_model.agent.name, name)
        value = getattr(agent_settings, name)
        print("value", value, name)
        if value  is not None:
            print("agent _get_agent_setting", name, value)
            if isinstance(value, (str, int, bool, GenericContent, BaseModel)):
                print("agent _get_agent_setting", name, value)
                return value
            if isinstance(value, (list,)):
                if "*" not in value: # overwrite parent list 
                    return value
                extend_at_index = value.index("*")
            else:
                raise Exception(f"_get_agent_setting does not yet support type of '{name}': {type(value)}")
        print("foo")
        #for extendsAgentVersion in self.extends_agent_versions.all():
        print(agent_version_model.extends_agent_versions.all())
        for extendsAgentVersion in agent_version_model.extends_agent_versions.all():
            print("extendsAgentVersion", extendsAgentVersion)
            ext_value =  extendsAgentVersion.get_runtime()._get_agent_setting(name)
            print("ext_value", ext_value)
            if ext_value is not None:
                if isinstance(value, (list,)) and extend_at_index is not None:
                    value[extend_at_index:extend_at_index+1] = ext_value
                else:
                    print("reutnr ext", ext_value)
                    return ext_value
        print("agent _get_agent_setting", name, value)
        return value
    
    def get_command(self, name):
        agent_version_model = self.get_version_model()
        TaskDefinition.objects.filter(name=name, task_type=TaskType.COMMAND, parent_agent=self.model)
        TaskDefinition.objects.filter(name=name, task_type=TaskType.COMMAND, parent_project=self.model.parent_project)
        
    
    def _get_agent_property(self, name:str) -> Any:
        return self.get_version_model()._resolve_property(name)

    def get_version_model(self) -> AgentVersionModel:
        if self._pinned_agent_version:
            return self._pinned_agent_version 
        return self.model.latest_agent_version
    
    def _set_version(self, agent_version: AgentVersionModel):
        self._pinned_agent_version = agent_version

    def all_versions(self):
        pass

