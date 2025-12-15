import inspect
import os
from agents.models.agent import Agent
from agents.models.agent_instance import AgentInstance
from core.models.prompt import Prompt
from core.models.prompt_relation import AgentPromptRelation
from events.models.event_handler import EventHandler
from events.models.event_subscription import EventSubscription, ExecutionMode
from events.models.event_type import EventTypes
from providers.models.ai_model import AiModel
from agents.models.agent_instance import AgentInstance
from dataclasses import dataclass
from typing import Any


@dataclass
class CommandConfig:
    command_name: str
    role: str
    description: str
    function_name: str
    match: Any = None
@dataclass
class EventHandlerConfig:
    event: str
    description: str
    executionMode: str
    function_name: str


class EventHandlers():
    Types = EventTypes
    available_commands = []
    available_handlers = []

    def __init__(self, agentInstance):
        self.agentInstance = agentInstance
        self.available_commands = []
        self.available_handlers = []
        #print("__init__. EventHandlers", )

        for attr_name in dir(self.__class__):
            attr = getattr(self.__class__, attr_name)
            #print("attr", attr, callable(attr), hasattr(attr, "_commandConfig") )
            #print("all:", dir(attr))
            if callable(attr) and hasattr(attr, "_commandConfig"):
                self.available_commands.append(getattr(attr, "_commandConfig" ))
        for attr_name in dir(self.__class__):
            attr = getattr(self.__class__, attr_name)
            if callable(attr) and hasattr(attr, "_handlerConfig"):
                self.available_handlers.append(getattr(attr, "_handlerConfig" ))
        self.__class__.available_commands =  self.available_commands
        self.__class__.available_handlers =  self.available_handlers

        #print(agentInstance, "available_commands", self.available_commands)
        #print(agentInstance, "available_handlers", self.available_handlers)

    @staticmethod
    def eventhandler(event, executionMode = ExecutionMode.BLOCKING, description = ""):
        print("eventhandler Decorator", event, executionMode, description)

        def wrapper(fn):
            print(fn)
            print(type(fn))
            fn._handlerConfig = EventHandlerConfig(
                event = event,
                description = description,
                executionMode = executionMode,
                function_name = fn.__name__,
            ) 
            print("FOO2", fn, fn.__name__, fn._handlerConfig)
            return fn
            
        return wrapper
    
    @staticmethod
    def command(role, match, name, description):
        print("Commnd Decorator", role, match, name, description)
        def wrapper(fn):
            print("Commnd Decorator CALL", fn, role, match, name, description)
            fn._commandConfig = CommandConfig(
                command_name = name,
                role = role,
                match = match,
                description = description,
                function_name = fn.__name__
            ) 
            print("FOO1", fn, fn.__name__, fn._commandConfig)
            return fn
        return wrapper

    def _parse_conversationMessage(self, agent, agentInstance, conversationMessage):
        fps = conversationMessage.conversationMessageParts.all()
        print("_parse_conversationMessage _parse_conversationMessage _parse_conversationMessage")
        if not fps:
            print("No FPS")
            return
        print(self.available_commands)
        for command in self.available_commands :
            print("command", command, conversationMessage.role)
            if command.role and conversationMessage.role != command.role:
                continue
            print(command.match)
            if not command.match(parts=fps):
                continue
            print("matched ")
            if conversationMessage.trigger_query:
                conversationMessage.trigger_query = False
                conversationMessage.save()
            print("SElf", self)
            f = getattr(self, command.function_name )
            r=f(command)
            print("R", command.function_name, r)


class AgentConfig():
    class EventHandlers(EventHandlers): pass

    @classmethod
    def create_instance(cls, instance_name=None, workingdir=None, parent_instance=None, event_subscriptions = []):
        print("create_instance", cls)
        i = cls(instance_name, workingdir, parent_instance, event_subscriptions)
        return i.instance
    
    def __init__(self, instance_name=None, workingdir=None, parent_instance=None, event_subscriptions = []):
        self.aimodel = None
        self.agent = None
        self.instance = None
        self.name = "" if not hasattr(self, "name") else self.name
        self.description =  "" if not hasattr(self, "description") else self.description
        self.input_schema = [] if not hasattr(self, "input_schema") else self.input_schema
        self.output_schema = [] if not hasattr(self, "output_schema") else self.output_schema
        self.system_prompt = "" if not hasattr(self, "system_prompt") else self.system_prompt
        self.task_prompt = "" if not hasattr(self, "task_prompt") else self.task_prompt
        self.model = "" if not hasattr(self, "model") else self.model
        self.EventHandlers = "" if not hasattr(self, "EventHandlers") else self.EventHandlers
        print("MODEL", self.model, self, self.name)
        self.aimodel = AiModel.objects.get(name=self.model)  if self.model else None
        # AGENT
        self.agent, _ = Agent.objects.update_or_create(
            name = self.name,
            defaults = {
                "limit_max_conversation_messages": 1,
                "limit_max_new_conversation_messages": 1,
                "description": self.description,
                "aimodel": self.aimodel,
            }
        )

        # FILL MISSING VALUES
        if not instance_name:
            instance_name = f"{self.agent.name}:{self.agent.pk} Instance of parent:{parent_instance.pk}" if parent_instance else "Default instance"
        if not workingdir and parent_instance:
            workingdir = parent_instance.workingdir
        if workingdir:
            workingdir = self._get_abs_path(workingdir)

        # INSTANCE
        print("GHERE2", parent_instance, workingdir)
        if  parent_instance == workingdir == None:
            raise Exception("here")
        self.instance, _ = AgentInstance.objects.update_or_create(
            agent = self.agent, 
            name = instance_name,
            defaults = {
                "parent": parent_instance,
                "workingdir": workingdir, 
            }
        )
        h = self.EventHandlers(self.instance)
        print("I_nsTA_NCE", self.instance)
        # SYSTEM PROMPT
        if self.system_prompt:
            pv =  Prompt.get_or_create_template(owner=self.agent.owners.first(), source=f"Agent", key="system", value=self.system_prompt, agent=self.agent )
            AgentPromptRelation.objects.update_or_create(
                role = "system",
                agent = self.agent,
                defaults = {
                    "prompt": pv.prompt,
                    "insert_at":  "TOP"
                }
            )
        # TASK PROMPT
        if self.task_prompt:
            print("HERER23", self.task_prompt, self.task_prompt )
            Prompt.get_or_create_template(owner=self.agent.owners.first(), source=f"Agent", key="task", value=self.task_prompt, agent=self.agent)
        
        # COMMAND RECEIVER EVENT HANDLER
        eventHandler, created = EventHandler.objects.update_or_create(
            receiver_agent = self.agent, # event receiver agent or agentInstance, 
            event = EventTypes.conversationMessage_added.instance(),
            name = f"UserCommandHandler",
            defaults = {
                "source_path": self._get_abs_path(inspect.getsourcefile(self.EventHandlers)),
                "source_function_name": self.EventHandlers.__qualname__ + "._parse_conversationMessage",
            },
        )
        print("FOO23;",  eventHandler, created)
        eventSubscription, _ = EventSubscription.objects.update_or_create(
            emitter_agentInstance = self.instance,
            receiver_agentInstance = self.instance,
            eventHandler = eventHandler,
            defaults = {
                "execution_mode": ExecutionMode.BLOCKING,
            }
        )

        eh = self.EventHandlers(self.instance)
        print("eh.available_handlers", self.name, eh.available_handlers)
        # event hanlders:
        for available_handler in eh.available_handlers:
            eventHandler, created = EventHandler.objects.update_or_create(
                receiver_agent = self.agent, # event receiver agent or agentInstance, 
                event = available_handler.event.instance(),
                name = available_handler.function_name,
                defaults = {
                    "description": available_handler.description,
                    "source_path": self._get_abs_path(inspect.getsourcefile(self.EventHandlers)),
                    "source_function_name": self.EventHandlers.__qualname__ + "." + available_handler.function_name,
                },
            )
            eventSubscription, _ = EventSubscription.objects.update_or_create(
                emitter_agentInstance = self.instance,
                receiver_agentInstance = self.instance,
                eventHandler = eventHandler,
                defaults = {
                    "execution_mode": available_handler.executionMode,
                }
            )
            available_handler.executionMode



        self.setup(self.instance)        
        for event_subscription in event_subscriptions:
            self.add_event_subscription(event_subscription["emitter"], event_subscription["event"], event_subscription["target"])
    
    def add_event_subscription(self, emitter, event, target, execution_mode=ExecutionMode.BLOCKING):  
        source = {}
        print(emitter, event, target, execution_mode)
        if callable(target) and target.__name__ == "<lambda>":
            function_name = event.name
            s = inspect.getsource(target)
            _args, _func = s.split("lambda",1)[1].split(":",1)
            source["source_string"] = f'def {function_name.strip()}({_args.strip()}):\n  return {_func.strip()}\n'
            source["source_function_name"] = f"{function_name.strip()}" 
        else:
            function_name = target.__name__
            source["source_function_name"] = target.__qualname__
            source["source_path"] = self._get_abs_path(inspect.getsourcefile(target))
  
        eventHandler, _ = EventHandler.objects.update_or_create(
            receiver_agent = self.agent, 
            event = event.instance(),
            name = function_name,
            defaults = {
                **source,
            }
        )
        emitter_agent = None
        emitter_agentInstance = None
        print("FOOBAR")
        if isinstance(emitter, Agent):
            emitter_agent = emitter
            print("emitter_agent", emitter_agent)
        elif isinstance(emitter, AgentInstance):
            emitter_agentInstance = emitter
            print("emitter_agentInstance", emitter_agentInstance)
        elif isinstance(emitter, AgentConfig):
            emitter_agentInstance = emitter.instance
            print("emitter_agentInstanceAgentConfig", emitter_agentInstance)
        print("receiver_agentInstance", self.instance)
        eventSubscription, _ = EventSubscription.objects.update_or_create(
            emitter_agent         = emitter_agent,
            emitter_agentInstance = emitter_agentInstance,
            receiver_agentInstance = self.instance,
            eventHandler = eventHandler,
            defaults = {
                "execution_mode": execution_mode,
            }
        )

    def _get_abs_path(self, path):
        path = os.path.expandvars(os.path.expanduser(path))
        if not os.path.isabs(path):
            path = os.path.join(os.path.realpath(os.path.abspath(os.path.expandvars(os.path.expanduser(os.getcwd())))), path)
        return os.path.realpath(os.path.abspath(path))
    
    def setup(self, instance):
        pass 

