from __future__ import annotations
import ast
from typing import List, Any, Dict
from typing import TYPE_CHECKING

from runtime.agents.bound_task import BoundTask
from server.models.content import GenericContent
from server.models.message import Message
from server.models.providers.ai_model import AiModel
from server.models.settings import ReasoningEffort, SettingsModel
from server.models.skills.skill_version import SkillModelVersion
from server.models.tasks.task_definition import TaskDefinition

from server.models.sessions.session import SessionModel
from server.models.tasks.task_definition_version import TaskDefinitionVersion

if TYPE_CHECKING:
    from server.models.sessions.session_version import SessionVersionModel

class Session():
    def __init__(self, session_model: SessionModel, pinned_session_version: SessionVersionModel|None = None):

        if not isinstance(session_model, SessionModel):
            raise Exception("foo23")
        self.model = session_model
        self._pinned_session_version = pinned_session_version

    @property
    def agent(self): 
        return self.get_version_model().agent.get_runtime()
    def set_agent(self, agent):
        self._set_session_property("agent", agent)

    # FROM INSTANCE
    @property
    def name(self): 
        return self.model.name
    
    # From Session version
    @property
    def description(self): 
        return self.get_version_model().description
    
    @property
    def workspace(self): 
        return self.get_version_model().workspace
    def set_workspace(self, value) -> None:
        self._set_session_property("workspace", value)


    @property
    def version_number(self): 
        return self.get_version_model().version_number
    
    # FROM Agent Version Setting
    @property
    def aimodel(self) -> AiModel|None:
        return self._get_session_setting("aimodel")
    def set_aimodel(self, model):
        self._set_session_setting("aimodel", model)

    @property
    def reasoning_effort(self) -> ReasoningEffort:
        return self._get_session_setting("reasoning_effort") or ReasoningEffort.NONE
    def set_reasoning_effort(self, value) -> None:
        self._set_session_setting("reasoning_effort", value)


    @property
    def max_retries(self) -> int:
        return self._get_session_setting("max_retries")
    @property
    def max_turns(self) -> int:
        return self._get_session_setting("max_turns")
    @property
    def current_turn_count(self) -> int:
        return self.model.turn_count
    
    def count_turn(self):
        SessionModel.objects.filter(pk=self.model.pk).update(turn_count=self.model.turn_count+1)
    def reset_turn_count(self):
        SessionModel.objects.filter(pk=self.model.pk).update(turn_count=0)



    @property
    def max_unattended_turns(self) -> int:
        return self._get_session_setting("max_unattended_turns")    
    @property
    def current_unattended_turn_count(self) -> int:
        return self.model.unattended_turn_count
    def count_unattended_turn(self):
        SessionModel.objects.filter(pk=self.model.pk).update(unattended_turn_count=self.model.turn_count+1)
    def reset_unattended_turn_count(self):
        try:
            SessionModel.objects.filter(pk=self.model.pk).update(unattended_turn_count=0)
        except Exception as e:
            print("Failed to update", e)

    @property
    def max_history_messages(self) -> int:
        return self._get_session_setting("max_history_messages")
    @property
    def priority(self) -> int:
        return self._get_session_setting("priority")

    @property
    def task_prompt(self) -> str|None:
        tp:GenericContent = self._get_session_setting("task_prompt")
        return  tp.get() if tp and isinstance(tp, GenericContent) else tp
    @property
    def system_prompt(self) -> str|None:
        sp:GenericContent = self._get_session_setting("system_prompt")
        return sp.get() if sp and isinstance(sp, GenericContent) else sp

    @property
    def scheduler_strategy(self) -> str|None:
        return self._get_session_setting("scheduler_strategy")
    @property
    def tool_call_syntax(self) -> str|None:
        return self._get_session_setting("tool_call_syntax")

    @property
    def commandNames(self) -> list[str]:
        return self._get_session_setting("commandNames") or []
    @property
    def disallowedCommandNames(self) -> list[str]:
        return self._get_session_setting("disallowedCommandNames") or []
    @property
    def allowedCommandNames(self) -> list[str]:
        return list(set(self.commandNames) - set(self.disallowedCommandNames))
    @property
    def allowedCommands(self) -> list[TaskDefinitionVersion]:
        return [t for t in [ self.agent.get_command(name) for name in self.allowedCommandNames] if t]
    
    def get_command(self, name) -> BoundTask|None:
        if name in self.allowedCommandNames:
            task_definition_version = self.agent.get_command(name)
            if task_definition_version:
                return BoundTask(session=self, task_definition_version=task_definition_version)
        return None
    
    @property
    def taskNames(self) -> list[str]:
        return self._get_session_setting("taskNames") or []
    @property
    def disallowedTaskNames(self) -> list[str]:
        return self._get_session_setting("disallowedTaskNames") or []
    @property
    def allowedTaskNames(self) -> list[str]:
        return list(set(self.taskNames) - set(self.disallowedTaskNames))
    @property
    def allowedTasks(self) -> list[TaskDefinitionVersion]:
        return [t for t in [ self.agent.get_task(name) for name in self.allowedTaskNames] if t]
    
    def get_task(self, name) -> BoundTask|None:
        if name in self.allowedTaskNames:
            task_definition_version = self.agent.get_task(name)
            if task_definition_version:
                return BoundTask(session=self, task_definition_version=task_definition_version)
        return None
    
    @property
    def toolNames(self) -> list[str]:
        return self._get_session_setting("toolNames") or []
    @property
    def disallowedToolNames(self) -> list[str]:
        return self._get_session_setting("disallowedToolNames") or []
    @property
    def allowedToolNames(self) -> list[str]:
        return list(set(self.toolNames) - set(self.disallowedToolNames))
    @property
    def allowedTools(self) -> list[TaskDefinitionVersion]:
        return [t for t in [ self.agent.get_tool(name) for name in self.allowedToolNames] if t]
    
    def get_tool(self, name) -> BoundTask|None:
        if name in self.allowedToolNames:
            task_definition_version = self.agent.get_tool(name)
            if task_definition_version:
                return BoundTask(session=self, task_definition_version=task_definition_version)
        return None
    
    @property
    def skillNames(self) -> list[str]:
        return self._get_session_setting("skillNames") or []
    @property
    def disallowedSkillNames(self) -> list[str]:
        return self._get_session_setting("disallowedSkillNames") or []
    @property
    def allowedSkillNames(self) -> list[str]:
        return list(set(self.skillNames) - set(self.disallowedSkillNames))
    
    def get_skill(self, name) -> SkillModelVersion|None:
        if name in self.allowedSkillNames:
            return self.agent.get_skill(name)
        return None
    
    def _get_session_setting(self, name) -> Any:
        session_version_model = self.get_version_model()
        agent_version = session_version_model.pinned_agent_version
        if not agent_version:
            agent_version = session_version_model.agent.latest_agent_version
        if not agent_version:
            raise Exception("some error")
        agent_settings_value = agent_version.resolve_setting(name)

        session_settings = session_version_model.session_settings
        if not session_settings:  # we overwrite nothing, use agents profile
            return agent_settings_value
        
        # we might overwrite agent profile values
        session_settings_value = getattr(session_settings, name)
        if session_settings_value is None: # we dont..
            return agent_settings_value 

        if isinstance(session_settings_value, (str, int, bool, GenericContent)):
            return session_settings_value
            
        if isinstance(session_settings_value, (list,)):
            if "*" not in session_settings_value: # overwrite parent list 
                return session_settings_value
            extend_at_index = session_settings_value.index("*")
            session_settings_value[extend_at_index:extend_at_index+1] = agent_settings_value
        else:
            raise Exception(f"_get_session_setting does not yet support type of '{name}': {type(session_settings_value)}")
        
        return session_settings_value

    def _set_session_setting(self, name, value):
        session_version_model = self.get_version_model()
        if not session_version_model.session_settings:
            new_session_setting = SettingsModel()
        else:
            new_session_setting = session_version_model.session_settings
        
        if getattr(new_session_setting, name) == value:
            return
        new_session_setting.pk = None
        new_session_setting.created_at = None
        new_session_setting.__setattr__(name, value)
        new_session_setting.save()
        session_version_model.pk = None
        session_version_model.created_at = None
        session_version_model.version_number += 1
        session_version_model.save()
        self.model.latest_session_version = session_version_model
        self.model.save()

    def _set_session_property(self, name, value):
        session_version_model = self.get_version_model()
        if getattr(session_version_model, name) == value:
            return 
        session_version_model.pk = None
        session_version_model.created_at = None
        session_version_model.version_number += 1
        session_version_model.__setattr__(name, value)
        session_version_model.save()
        self.model.latest_session_version = session_version_model
        self.model.save()

    def get_version_model(self) -> SessionVersionModel:
        if self._pinned_session_version:
            return self._pinned_session_version 
        #print(self.model)
        return self.model.latest_session_version 
    
    def add_user_message(self,  parts: List[Dict]|None = None):
        '''
        parts:  list from parse_llm_response of Parts
            Parts is dict with minimal keys:
                type: message, reasoning, toolcall
                content_type: text|image|template|json
                content: str|dict
        '''
        if not parts:
            raise Exception("No message or message parts provided")

        if parts[0] and parts[0].get("content", [None,])[0] == "!": # might be command
            cmd = parts[0].get("content", [None,]).split(None,1)[0][1:].strip()  # Get command without '!'
            print("CMD", cmd)
            bound_cmd = self.get_command(cmd)
            if bound_cmd:
                full_cmd_str = "".join([part["content"] for part in parts]).strip() if parts else ""
                cmd_payload = full_cmd_str[1+len(cmd):].strip()
                # Safely parse arguments and keyword arguments
                _payload_ast_tree = ast.parse(f"f({cmd_payload})")
                call = _payload_ast_tree.body[0].value if _payload_ast_tree.body else None
                args = [ast.literal_eval(arg) for arg in call.args] if call else []
                kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords} if call else {}

                # Schedule command execution
                bound_cmd.delay(*args, **kwargs)
                # TODO
                return self.handle_user_command.delay(conversation_msg, cmd, cmdargs = args, cmdkwargs = kwargs)

            print("NOT TASK!")

        return self.get_task("ingest_user_message").delay(parts = parts)

    def get_messages(self):
        return Message.objects.filter(session_version__session=self.model, )
