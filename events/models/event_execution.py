
import sys
from agents.models.agent import Agent
from agents.models.agent_instance import AgentInstance, AgentTask
from agents.models.conversation_message import ConversationMessage, ConversationMessagePart
from core.models.base_model import BaseModel
from django.db import models
import os, json
from importlib.machinery import SourceFileLoader
from pathlib import Path
from tools.builtin_kv_storage.models.kv_item import KVItem


class EventExecution(BaseModel):
    class EventExecutionStatus(models.TextChoices):
        PENDING = 'PENDING', 'pending execution'
        ACTIVE = 'ACTIVE', 'active'
        FAILED = 'FAILED', 'failed'
        SUCCESS = 'SUCCESS', 'success'

    eventHandler = models.ForeignKey("events.EventHandler", default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    eventSubscription = models.ForeignKey("events.EventSubscription", default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    status = models.CharField(max_length=100, choices=EventExecutionStatus.choices, default=EventExecutionStatus.PENDING)

    # arguments the event is called with
    agent = models.ForeignKey(Agent, default=None, on_delete=models.CASCADE, related_name='related_events', null=True, blank=True)
    agentInstance = models.ForeignKey("agents.AgentInstance", default=None, on_delete=models.CASCADE, related_name='related_events', null=True, blank=True)
    conversationMessage = models.ForeignKey("agents.ConversationMessage", default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    llmQuery = models.ForeignKey("agents.LLMQuery", default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    llmResponse = models.ForeignKey("agents.LLMResponse", default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    toolCall =  models.ForeignKey("calls.toolCall", default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    agentTask =  models.ForeignKey("agents.agentTask", default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    agentChildTasks =  models.ManyToManyField("agents.agentTask", default=None, related_name='related_parent_events', null=True, blank=True)

    def as_client_dict(self):
        return {
            'object': 'EventSubscription',
            'id': self.pk,
            'eventHandler_id': self.eventHandler_id,
        }

    def run(self):

        print("HEREHERE", self)
        kwargs = {}
        for arg in ["agent", "agentInstance", "conversationMessage", "llmQuery", "llmResponse", "toolCall", "agentTask"]:
            if value := getattr(self, arg): 
                kwargs[arg] = value
        if self.agentChildTasks.all().count() > 0:
            kwargs["agentChildTasks"] = list(self.agentChildTasks.all())
        self.status = EventExecution.EventExecutionStatus.ACTIVE
        self.save()
        new_status = EventExecution.EventExecutionStatus.FAILED
        '''
        EvSub:Emitter   EvHandler:Receiver    Description    (
        AgentA          AgentB              Event emitted by any instance of AgentA is received by a instance of AgentB. This AgentB Instance will be created if it does not exist
        AgentA          AgentBInstance      Event emitted by any instance of AgentA is received by AgentInstanceB
        AgentAInstance  AgentB              Event emitted by         AgentAInstance is received by a instance of AgentB. This AgentB Instance will be created if it does not exist
        AgentAInstance  AgentBInstance      Event emitted by         AgentAInstance is received by AgentBInstance
        if new agentInstance must be created:
            create_one_receiverAgentInstance_per_emitterAgentInstance
            create_one_receiverAgentInstance_per_emitterAgent
            create_one_receiverAgentInstance_globally
        '''
        
        #else:
        #    t = "create_one_receiverAgentInstance_per_emitterAgentInstance"
        #    if t == "create_one_receiverAgentInstance_per_emitterAgentInstance":
        #        n = f"EventHandler_pk:{self.eventHandler.pk}, EmitterAgentInstance_pk:{self.agentInstance.pk}"
        #    elif t == "create_one_receiverAgentInstance_per_emitterAgent":
        #        n = f"EventHandler_pk:{self.eventHandler.pk}, EmitterAgent_pk:{self.agent.pk}"
        #    elif t == "create_one_receiverAgentInstance_globally":
        #        n = f"EventHandler_pk:{self.eventHandler.pk}"
        #    receiver_agentInstance = self.eventHandler.receiver_agent.update_or_create_instance(
        #        instance_name = n,
        #        workingdir = self.agentInstance.workingdir,
        #        parent_instance = self.agentInstance,
        #    )
        receiver_agentInstance = self.eventSubscription.receiver_agentInstance
        try:
            if self.eventHandler.source_string:
                env = { 
                    "event": self,
                    "Agent": Agent,
                    "KVItem": KVItem,
                    "AgentInstance": AgentInstance,
                    "AgentTask": AgentTask,
                    "ConversationMessage": ConversationMessage,
                    "ConversationMessagePart": ConversationMessagePart,
                    "os": os, "Path": Path,  "json": json, "sys": sys
                }
                exec(self.eventHandler.source_string, env, env)
                print("HERE RUN1", kwargs)
                f = env.get(self.eventHandler.source_function_name)
                f(receiver_agentInstance, **kwargs)
            else:
                full_name = self.eventHandler.source_function_name
                function_name = full_name.split(".")[-1]
                tmp_cls = SourceFileLoader(f"dynamic_scripts.{Path(self.eventHandler.source_path).stem}", self.eventHandler.source_path).load_module()
                for part in full_name.split(".")[:-1]:
                    tmp_cls = getattr(tmp_cls, part)
                classInstance = tmp_cls(receiver_agentInstance)
                print("HERE RUN", self, full_name, kwargs)
                f = getattr(classInstance, function_name)
                f(**kwargs)
                
            print("success", f)
            new_status = EventExecution.EventExecutionStatus.SUCCESS
        except Exception as e:
            print(e)
            if self.eventSubscription and self.eventSubscription.ignore_error:
                return
            raise e
        finally:
            self.status = new_status
            self.save()
