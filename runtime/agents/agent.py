from __future__ import annotations
from typing import List, Any, Dict, Union

from server.models.content import GenericContent
from typing import TYPE_CHECKING

from server.models.skills.skill_version import SkillModelVersion
from server.models.tasks.task_definition_version import TaskDefinitionVersion

if TYPE_CHECKING:
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.agents.agent import AgentModel

class Agent():
    def __init__(self, agent_model:AgentModel, pinned_agent_version: AgentVersionModel|None = None ):
        self.model:AgentModel = agent_model
        self._pinned_agent_version = pinned_agent_version
    
    # FROM AGENT
    @property
    def name(self): 
        return self.model.name
  
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
        return self.get_version_model().resolve_setting("aimodel")
    @property
    def max_retries(self) -> int:
        return self.get_version_model().resolve_setting("max_retries")
    @property
    def max_turns(self) -> int:
        return self.get_version_model().resolve_setting("max_turns")
    @property
    def max_unattended_turns(self) -> int:
        return self.get_version_model().resolve_setting("max_unattended_turns")
    @property
    def max_history_messages(self) -> int:
        return self.get_version_model().resolve_setting("max_history_messages")
    @property
    def priority(self) -> int:
        return self.get_version_model().resolve_setting("priority")
        
    @property
    def scheduler_strategy(self) -> str:
        return self.get_version_model().resolve_setting("scheduler_strategy")
    @property
    def tool_call_syntax(self) -> str:
        return self.get_version_model().resolve_setting("tool_call_syntax")
    
    @property
    def task_prompt(self) -> str:
        tp = self.get_version_model().resolve_setting("task_prompt")
        if tp and isinstance(tp, GenericContent):
            return tp.get()
        return tp
    @property
    def system_prompt(self) -> str:
        sp = self.get_version_model().resolve_setting("system_prompt")
        if sp and isinstance(sp, GenericContent):
            return sp.get()
        return sp
    

    @property
    def commandNames(self) -> list[str]:
        return self.get_version_model().resolve_setting("commandNames") or []
    @property
    def disallowedCommandNames(self) -> list[str]:
        return self.get_version_model().resolve_setting("disallowedCommandNames") or []
    @property
    def allowedCommandNames(self) -> list[str]:
        return list(set(self.commandNames) - set(self.disallowedCommandNames))
    @property
    def allowedCommands(self) -> list[TaskDefinitionVersion]:
        return [t for t in [ self.get_command(name) for name in self.allowedCommandNames] if t]
    
    def get_command(self, name) -> TaskDefinitionVersion|None:
        if name in self.allowedCommandNames:
            return self.get_version_model().commands().filter(task_definition__name=name).first()
        return None  
    

    @property
    def taskNames(self) -> list[str]:
        return self.get_version_model().resolve_setting("taskNames") or []
    @property
    def disallowedTaskNames(self) -> list[str]:
        return self.get_version_model().resolve_setting("disallowedTaskNames") or []
    @property
    def allowedTaskNames(self) -> list[str]:
        return list(set(self.taskNames) - set(self.disallowedTaskNames))
    @property
    def allowedTasks(self) -> list[TaskDefinitionVersion]:
        return [t for t in [ self.get_task(name) for name in self.allowedTaskNames] if t]
    
    def get_task(self, name) -> TaskDefinitionVersion|None:
        if name in self.allowedTaskNames:
            return self.get_version_model().tasks().filter(task_definition__name=name).first()
        return None  


    @property
    def toolNames(self) -> list[str]:
        return self.get_version_model().resolve_setting("toolNames") or []
    @property
    def disallowedToolNames(self) -> list[str]:
        return self.get_version_model().resolve_setting("disallowedToolNames") or []
    @property
    def allowedToolNames(self) -> list[str]:
        return list(set(self.toolNames) - set(self.disallowedToolNames))
    @property
    def allowedTools(self) -> list[TaskDefinitionVersion]:
        return [t for t in [ self.get_tool(name) for name in self.allowedToolNames] if t]
    
    def get_tool(self, name) -> TaskDefinitionVersion|None:
        if name in self.allowedToolNames:
            return self.get_version_model().tools().filter(task_definition__name=name).first()
        return None
    

    @property
    def skillNames(self) -> list[str]:
        return self.get_version_model().resolve_setting("skillNames") or []
    @property
    def disallowedSkillNames(self) -> list[str]:
        return self.get_version_model().resolve_setting("disallowedSkillNames") or []
    @property
    def allowedSkillNames(self) -> list[str]:
        return list(set(self.skillNames) - set(self.disallowedSkillNames))
    @property
    def allowedSkills(self) -> list[SkillModelVersion]:
        return [t for t in [ self.get_skill(name) for name in self.allowedSkillNames] if t]
    
    def get_skill(self, name) -> SkillModelVersion|None:
        if name in self.allowedSkillNames:
            return self.get_version_model().skills().filter(skill__name=name).first()
        return None


    @property
    def subagentNames(self) -> list[str]:
        return self.get_version_model().resolve_setting("subagentNames") or []
    @property
    def disallowedSubagentNames(self) -> list[str]:
        return self.get_version_model().resolve_setting("disallowedSubagentNames") or []
    @property
    def allowedSubagentNames(self) -> list[str]:
        return list(set(self.subagentNames) - set(self.disallowedSubagentNames))
    @property
    def allowedSubagents(self) -> list[AgentVersionModel]:
        return [s for s in [self.get_subagent(name) for name in self.allowedSubagentNames] if s]

    def get_subagent(self, name) -> AgentVersionModel|None:
        if name in self.allowedSubagentNames:
            return self.get_version_model().subagent_versions.filter(agent__name=name).first()
        return None

    def subagent_config(self, name) -> dict:
        return self.get_version_model().subagent_configs.get(name, {})

    @property
    def definedSubagentVersions(self):
        return self.get_version_model().defined_subagent_versions.all()
    
    def _get_agent_property(self, name:str) -> Any:
        return self.get_version_model().resolve_property(name)

    def get_version_model(self) -> AgentVersionModel:
        if self._pinned_agent_version:
            return self._pinned_agent_version 
        return self.model.latest_agent_version
    