from __future__ import annotations
import ast
from typing import List, Any, Dict
from typing import TYPE_CHECKING

from runtime.agents.bound_task import BoundTask
from server.models.content import GenericContent
from server.models.message import Message
from server.models.providers.ai_model import AiModel
from server.models.settings import ReasoningEffort, SettingsModel
from server.models.tasks.task_definition import TaskDefinition

if TYPE_CHECKING:
    from server.models.sessions.session_version import SessionVersionModel
    from server.models.sessions.session import SessionModel
    from server.models.agents.agent_version import AgentVersionModel

class Session():
    def __init__(self, session_model: SessionModel, pinned_session_version: SessionVersionModel|None = None):
        from server.models.sessions.session import SessionModel

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
        from server.models.sessions.session import SessionModel
        SessionModel.objects.filter(pk=self.model.pk).update(turn_count=self.model.turn_count+1)
    def reset_turn_count(self):
        from server.models.sessions.session import SessionModel

        SessionModel.objects.filter(pk=self.model.pk).update(turn_count=0)

    

    @property
    def max_unattended_turns(self) -> int:
        return self._get_session_setting("max_unattended_turns")    
    @property
    def current_unattended_turn_count(self) -> int:
        return self.model.unattended_turn_count
    def count_unattended_turn(self):
        from server.models.sessions.session import SessionModel

        SessionModel.objects.filter(pk=self.model.pk).update(unattended_turn_count=self.model.turn_count+1)
    def reset_unattended_turn_count(self):
        try:
            from server.models.sessions.session import SessionModel

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
    def execution_mode(self) -> str|None:
        return self._get_session_setting("execution_mode")
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
    def taskNames(self) -> list[str]:
        return self._get_session_setting("taskNames") or []
    @property
    def disallowedTaskNames(self) -> list[str]:
        return self._get_session_setting("disallowedTaskNames") or []
    @property
    def allowedTaskNames(self) -> list[str]:
        return list(set(self.taskNames) - set(self.disallowedTaskNames))
    
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
    def skillNames(self) -> list[str]:
        return self._get_session_setting("skillNames") or []
    @property
    def disallowedSkillNames(self) -> list[str]:
        return self._get_session_setting("disallowedSkillNames") or []
    @property
    def allowedSkillNames(self) -> list[str]:
        return list(set(self.skillNames) - set(self.disallowedSkillNames))
    
    def _get_session_setting(self, name) -> Any:
        session_version_model = self.get_version_model()
        agent_settings_value = self.agent._get_agent_setting(name)

        if not session_version_model.session_settings:  # we overwrite nothing, use agents profile
            return agent_settings_value
        
        # we might overwrite agent profile values
        session_settings_value = getattr(self.session_settings, name)
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
    
    def _set_version(self, session_version: SessionVersionModel):
        self._pinned_session_version = session_version

    def all_versions(self):
        pass

    def add_user_message(self,  message: str|None = None, parts: List[Dict]|None = None):
        if parts is None and message is not None:
            parts = [{"content": message, "type": "TEXT"}]
        if not parts:
            raise Exception("No message or message parts provided")

        if parts[0] and parts[0].get("content", [None,])[0] == "!": # might be command
            cmd = parts[0].get("content", [None,]).split(None,1)[0][1:].strip()  # Get command without '!'
            task_function = None
            print("CMD", cmd)
            if cmd in self.allowedCommandNames:
                taskDefinition = TaskDefinition.objects.filter(name=cmd).first()

                full_cmd_str = "".join([part["content"] for part in parts]).strip() if parts else ""
                cmd_payload = full_cmd_str[1+len(cmd):].strip()
                # Safely parse arguments and keyword arguments
                _payload_ast_tree = ast.parse(f"f({cmd_payload})")
                call = _payload_ast_tree.body[0].value if _payload_ast_tree.body else None
                args = [ast.literal_eval(arg) for arg in call.args] if call else []
                kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords} if call else {}

                # Schedule command execution
                task = BoundTask(self.get_version_model(), taskDefinition)
                task.delay(*args, **kwargs)
                return self.handle_user_command.delay(conversation_msg, cmd, cmdargs = args, cmdkwargs = kwargs)

            print("NOT TASK!")
      
        return self.handle_user_message.delay(message=message, parts = parts)

    def __getattribute__(self, name: str) -> Any:
        try:
            return object.__getattribute__(self, name)
        except Exception as e:
            print(name, self.allowedTaskNames)
            task = None
            if name in self.allowedTaskNames:
                task = self.agent.get_allowed_task(name)
            elif name in self.allowedCommandNames:
                task = self.agent.get_allowed_command(name)
            elif name in self.allowedToolNames:
                task = self.agent.get_allowed_tool(name)
            
            if task:
                print("FOUND TASK", task)
                return BoundTask(self.get_version_model(), task)
            return object.__getattribute__(self, name)
            print("NAME NOT FOUND")
            raise Exception(f"Task '{name}' not found in {self}")

    def get_messages(self):
        return Message.objects.filter(session_version__session=self.model, )
        
      
    def commands(self):
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
        from server.models.agents.agent import AgentModel


        tasks = {}
        def resolve_task(agent_version: AgentVersionModel, task_name):
            print("resolve_task", agent_version, task_name)
            task = TaskDefinition.objects.filter(name=task_name, parent_agent = agent_version.agent).first()
            if task:
                tasks[task_name] = task
                return
            extends = agent_version.extends_agent_versions.all()
            print("extends", extends)
            for extend in extends:
                agent = AgentModel.objects.get(name=extend)
                agent_version = agent.latest_agent_version
                if agent_version:
                    resolve_task(agent_version, task_name )
        for allowed_task_name in self.allowedCommandNames:
            resolve_task(self.get_version_model().agent_version, allowed_task_name)
        print("TASKS TASKS", tasks)

        return TaskDefinition.objects.filter(pk__in=[ v.pk for k, v in tasks.items()])
