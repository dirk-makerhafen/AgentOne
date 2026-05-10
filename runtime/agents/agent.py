from __future__ import annotations
from typing import List, Any, Dict
import ast
from runtime.agents.bound_task import BoundTask
from runtime.agents.instance import Instance

from server.models.agents.agent_instance import InstanceModel
from server.models.content import GenericContent
from server.models.conversation_message import ConversationMessage
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.models.agents.agent_version import AgentVersionModel
    from server.models.agents.agent import AgentModel

from server.models.project import Project
from server.models.skill import Skill
'''
class AgentModel(BaseModel):
    """
    Uniquely identifies an Agent across all versions and variants.
    """
    name = models.CharField(max_length=255, unique=True)
    latest_agent_version = models.ForeignKey("server.AgentVersionModel", default=None, null=True, on_delete=models.SET_NULL, related_name='related_newest_version')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills

class AgentVersionModel(BaseModel):  
    parent_skill = models.ForeignKey("server.Skill", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
    parent_agent = models.ForeignKey("server.AgentModel", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */.agentone/Agent/someagent/skills/ , null for global skill in ~/.agentone/skills
    parent_project = models.ForeignKey("server.Project", default=None, null=True, on_delete=models.CASCADE, related_name='child_agents')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills
    
    agent = models.ForeignKey("server.AgentModel"        , on_delete=models.CASCADE, related_name="related_agent_versions")

    description = models.TextField(max_length=65500, default="")

    extendsAgents = models.ManyToManyField("server.AgentModel", related_name="related_inheritors", default=None, null=True)
    extendsAgentNames = models.JSONField(default=list, blank=True)

    agent_profile = models.ForeignKey("server.ProfileModel" ,default=None,null=True, on_delete=models.SET_NULL, related_name="related_agent_versions") # top level profile
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
class Projects():
    def __init__(self) -> None:
        pass
    def root(self):
        return Project.objects.all()
    
    
class Agents():
    def __init__(self) -> None:
        pass

    def root(self):
        from server.models.agents.agent import AgentModel
        return AgentModel.objects.filter(
            latest_agent_version__parent_skill = None, 
            latest_agent_version__parent_agent = None,
            latest_agent_version__parent_project = None
        )
    

class Instances():
    def __init__(self) -> None:
        pass
    def root(self):
        print("INSTANCES")

        i= InstanceModel.objects.filter(
            #latest_instance_version__agent_version__parent_skill = None, 
            #latest_instance_version__agent_version__parent_agent = None,
            #latest_instance_version__agent_version__parent_project = None
        )
        print(i)
        return i
    
class Skills():
    def __init__(self) -> None:
        pass
    def root(self):
        return Skill.objects.filter(
            #parent_skill = None, 
            #parent_agent = None,
            #parent_project = None
        )

class Agent():
    def __init__(self, agent_model:AgentModel, pinned_agent_version: AgentVersionModel|None = None ):
        self._agent_model = agent_model
        self._pinned_agent_version = pinned_agent_version
        
    def _get_version(self) -> AgentVersionModel:
        if self._pinned_agent_version:
            return self._pinned_agent_version 
        return self._agent_model.latest_agent_version
    
    def _set_version(self, agent_version: AgentVersionModel):
        self._pinned_agent_version = agent_version

    # FROM AGENT
    @property
    def name(self): 
        return self._agent_model.name
    
    # FROM AGENT VERSION
    @property
    def description(self): 
        return self._resolve_agent_value("description")
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
    def commandNames(self) -> list:
        return self._resolve_profile_value("commandNames")
    @property
    def disallowedCommandNames(self) -> list:
        return self._resolve_profile_value("disallowedCommandNames")
    @property
    def allowedCommandsNames(self) -> set:
        return set(self.commandNames) - set(self.disallowedCommandNames)
    
    @property
    def taskNames(self) -> list:
        return self._resolve_profile_value("taskNames")
    @property
    def disallowedTaskNames(self) -> list:
        return self._resolve_profile_value("disallowedTaskNames")
    @property
    def allowedTaskNames(self) -> set:
        return set(self.taskNames) - set(self.disallowedTaskNames)
    
    @property
    def toolNames(self) -> list:
        return self._resolve_profile_value("toolNames")
    @property
    def disallowedToolNames(self) -> list:
        return self._resolve_profile_value("disallowedToolNames")
    @property
    def allowedToolNames(self) -> set:
        return set(self.toolNames) - set(self.disallowedToolNames)

    @property
    def skillNames(self) -> list:
        return self._resolve_profile_value("skillNames")
    @property
    def disallowedSkillNames(self) -> list:
        return self._resolve_profile_value("disallowedSkillNames")
    @property
    def allowedSkillNames(self) -> set:
        return set(self.skillNames) - set(self.disallowedSkillNames)
    

    def _resolve_profile_value(self, name:str) -> Any:
        return self._get_version()._resolve_profile_value(name)
    
    def _resolve_agent_value(self, name:str) -> Any:
        return self._get_version()._resolve_agent_value(name)


    def all_versions(self):
        pass





    def __getattribute__(self, name: str) -> Any:
        try:
            return object.__getattribute__(self, name)
        except Exception as e:
            task = object.__getattribute__(self, "all_tasks")(filter=dict(name=name)).first()
            if task:
                return BoundTask(self, task)
            raise Exception(f"Task '{name}' not found in {self}")

    def all_tasks(self, filter:Dict={}):
        return self.tasks().filter(**filter).union(self.tools().filter(**filter)).union(self.commands().filter(**filter)).union(self.skills().filter(**filter))

    def tasks(self):
        return self.agent.latest_agent_version.tasks()

    def tools(self):
        return  self.agent.latest_agent_version.tools()

    def commands(self):
        return  self.agent.latest_agent_version.commands()

    def skills1(self):
        return  self.agent.latest_agent_version.skills()

    def add_user_message(self,  message: str|None = None, parts: List[Dict]|None = None):
        if parts is None and message is not None:
            parts = [{"content": message, "type": "TEXT"}]
        if not parts:
            raise Exception("No message or message parts provided")

        conversation_msg = ConversationMessage.objects.create(role = "user", agent_instance_version = self.agent_instance_version)
        if parts[0] and parts[0].get("content", [None,])[0] == "!": # might be command
            cmd = parts[0].get("content", [None,]).split(None,1)[0][1:].strip()  # Get command without '!'
            task_function = None
            print("CMD", cmd)
            taskdefinition = self.commands().filter(trigger=cmd).first()
            if not taskdefinition:
                taskdefinition = self.commands().filter(name=cmd).first()
            if not taskdefinition:
                taskdefinition = self.tools().filter(name=cmd).first()
            if not taskdefinition:
                taskdefinition = self.tasks().filter(name=cmd).first()

            if taskdefinition:
                task_function = self.__getattribute__(taskdefinition.name)
                print("task_function", task_function,  taskdefinition.name, task_function, taskdefinition.path)
            if task_function:

                full_cmd_str = "".join([part["content"] for part in parts]).strip() if parts else ""
                cmd_payload = full_cmd_str[1+len(cmd):].strip()
                # Safely parse arguments and keyword arguments
                _payload_ast_tree = ast.parse(f"f({cmd_payload})")
                call = _payload_ast_tree.body[0].value if _payload_ast_tree.body else None
                args = [ast.literal_eval(arg) for arg in call.args] if call else []
                kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in call.keywords} if call else {}
                return self.handle_user_command.delay(conversation_msg, cmd, cmdargs = args, cmdkwargs = kwargs)

            print("NOT TASK!")
        for part in parts:
            conversation_msg.add_part(part["content"])
        return self.handle_chat_message.delay(conversation_message=conversation_msg)

