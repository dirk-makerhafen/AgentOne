

from agents.models.agent import Agent
from agents.models.conversation_message import ConversationMessage, ConversationMessagePart
from agents.tasks.execute_event import execute_event
from core.models.base_model import BaseModel
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Q

class EventDispatcher():     
    @classmethod
    def event_agentinstance_created(cls, agent, agentInstance):
        cls._run_subscriptions(EventHandler.EventType.event_agentinstance_created, {"agent": agent, "agentInstance": agentInstance})   
    
    @classmethod
    def event_conversationMessage_added(cls, agent, agentInstance, conversationMessage):
        cls._run_subscriptions(EventHandler.EventType.event_conversationMessage_added, {"agent": agent, "agentInstance": agentInstance, "conversationMessage": conversationMessage})   
    
    @classmethod
    def event_llmquery_pre_create(cls, agent, agentInstance):
        cls._run_subscriptions(EventHandler.EventType.event_llmquery_pre_create, {"agent": agent, "agentInstance": agentInstance})   
    
    @classmethod
    def event_llmquery_post_create(cls, agent, agentInstance, llmQuery):
        cls._run_subscriptions(EventHandler.EventType.event_llmquery_post_create, {"agent": agent, "agentInstance": agentInstance, "llmQuery": llmQuery})   
    
    @classmethod
    def event_llmquery_pre_execute(cls, agent, agentInstance, llmQuery):
        cls._run_subscriptions(EventHandler.EventType.event_llmquery_pre_execute, {"agent": agent, "agentInstance": agentInstance, "llmQuery": llmQuery})   
    
    @classmethod
    def event_llmquery_successfull(cls, agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_subscriptions(EventHandler.EventType.event_llmquery_successfull, {"agent": agent, "agentInstance": agentInstance, "llmQuery": llmQuery, "llmResponse": llmResponse, "conversationMessage": conversationMessage})   
    
    @classmethod
    def event_llmquery_failed(cls, agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_subscriptions(EventHandler.EventType.event_llmquery_failed, {"agent": agent, "agentInstance": agentInstance, "llmQuery": llmQuery, "llmResponse": llmResponse, "conversationMessage": conversationMessage})   
    
    @classmethod
    def event_llmresponse_pre_parse(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_subscriptions(EventHandler.EventType.event_llmresponse_pre_parse, {"agent": agent, "agentInstance": agentInstance, "llmQuery": llmQuery, "llmResponse": llmResponse, "conversationMessage": conversationMessage})   
    
    @classmethod
    def event_llmresponse_post_parse(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_subscriptions(EventHandler.EventType.event_llmresponse_post_parse, {"agent": agent, "agentInstance": agentInstance, "llmQuery": llmQuery, "llmResponse": llmResponse, "conversationMessage": conversationMessage})   
    
    @classmethod
    def event_llmresponse_pre_tool_calls(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_subscriptions(EventHandler.EventType.event_llmresponse_pre_tool_calls, {"agent": agent, "agentInstance": agentInstance, "llmQuery": llmQuery, "llmResponse": llmResponse, "conversationMessage": conversationMessage})   
    
    @classmethod
    def event_llmresponse_pre_tool_call(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage, toolCall):
        cls._run_subscriptions(EventHandler.EventType.event_llmresponse_pre_tool_call, {"agent": agent, "agentInstance": agentInstance, "llmQuery": llmQuery, "llmResponse": llmResponse, "conversationMessage": conversationMessage, "toolCall": toolCall})   
    
    @classmethod
    def event_llmresponse_post_tool_call(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage, toolCall):
        cls._run_subscriptions(EventHandler.EventType.event_llmresponse_post_tool_call, {"agent": agent, "agentInstance": agentInstance, "llmQuery": llmQuery, "llmResponse": llmResponse, "conversationMessage": conversationMessage, "toolCall": toolCall})   
    
    @classmethod
    def event_llmresponse_post_tool_calls(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_subscriptions(EventHandler.EventType.event_llmresponse_post_tool_calls, {"agent": agent, "agentInstance": agentInstance, "llmQuery": llmQuery, "llmResponse": llmResponse, "conversationMessage": conversationMessage})   
    
    @classmethod
    def event_llmresponse_finished(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_subscriptions(EventHandler.EventType.event_llmresponse_finished, {"agent": agent, "agentInstance": agentInstance, "llmQuery": llmQuery, "llmResponse": llmResponse, "conversationMessage": conversationMessage})   

    @classmethod 
    def _run_subscriptions(cls, eventType, arguments):
        subscriptions = EventSubscription.objects.filter(Q(agent=arguments["agent"]) | Q(agentInstance=arguments["agentInstance"]), eventHandler__eventtype=eventType)
        for subscription in subscriptions:
            subscription.run(arguments)


class EventHandler(BaseModel):
    agent = models.ForeignKey(Agent, default=None, on_delete=models.CASCADE, related_name='event_receiver_functions', null=True, blank=True)
    agentInstance = models.ForeignKey("agents.AgentInstance", default=None, on_delete=models.CASCADE, related_name='event_receiver_functions', null=True, blank=True)

    class EventType(models.TextChoices):
        event_agentinstance_created = 'event_agentinstance_created', 'event_agentinstance_created(agent, agentInstance)'
        event_conversationMessage_added = 'event_conversationMessage_added', 'event_conversationMessage_added(agent, agentInstance, conversationMessage)'
        event_llmquery_pre_create = 'event_llmquery_pre_create', 'event_llmquery_pre_create(agent, agentInstance)'
        event_llmquery_post_create = 'event_llmquery_post_create', 'event_llmquery_post_create(agent, agentInstance, llmQuery)'
        event_llmquery_pre_execute = 'event_llmquery_pre_execute', 'event_llmquery_pre_execute(agent, agentInstance, llmQuery)'
        event_llmquery_successfull = 'event_llmquery_successfull', 'event_llmquery_successfull(agent, agentInstance, llmQuery, llmResponse, conversationMessage)'
        event_llmquery_failed = 'event_llmquery_failed', 'event_llmquery_failed(llmQuery, llmResponse, conversationMessage)'
        event_llmresponse_pre_parse = 'event_llmresponse_pre_parse', 'event_llmresponse_pre_parse(llmQuery, llmResponse, conversationMessage)'
        event_llmresponse_post_parse = 'event_llmresponse_post_parse', 'event_llmresponse_post_parse(llmQuery, llmResponse, conversationMessage)'
        event_llmresponse_pre_tool_calls = 'event_llmresponse_pre_tool_calls', 'event_llmresponse_pre_tool_calls(llmQuery, llmResponse, conversationMessage)'
        event_llmresponse_pre_tool_call = 'event_llmresponse_pre_tool_call', 'event_llmresponse_pre_tool_call(llmQuery, llmResponse, conversationMessage, toolcall)'
        event_llmresponse_post_tool_call = 'event_llmresponse_post_tool_call', 'event_llmresponse_post_tool_call(llmQuery, llmResponse, conversationMessage, toolcall)'
        event_llmresponse_post_tool_calls = 'event_llmresponse_post_tool_calls', 'event_llmresponse_post_tool_calls(llmQuery, llmResponse, conversationMessage)'
        event_llmresponse_finished = 'event_llmresponse_finished', 'event_llmresponse_finished(llmQuery, llmResponse, conversationMessage)'
        
    eventtype = models.CharField(max_length=100, choices=EventType.choices, default=EventType.event_agentinstance_created)
    name = models.CharField(default="",help_text="name", max_length=10000)
    description =  models.CharField(default="",help_text="description", max_length=100000)
    source = models.TextField(default="",help_text="sourcecode", max_length=100000)
    is_public = models.BooleanField(default=False, help_text="pubic")
    enabled = models.BooleanField(default=False, help_text="enabled")
    is_blocking = models.BooleanField(default=True, help_text="block until finished, otherwise detach")
    
    def as_client_dict(self):
        return {
            'object': 'EventHandler',
            'id': self.pk,
            'agent': {'pk': self.agent.pk, 'name': self.agent.name} if self.agent else None,
            'agentInstance': {'pk': self.agentInstance.pk} if self.agentInstance else None,
            'eventtype': self.eventtype,
            'name': self.name,
            'description': self.description,
            'source': self.source,
            'is_public': self.is_public,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        
class EventSubscription(BaseModel):
    agent = models.ForeignKey(Agent, default=None, on_delete=models.CASCADE, related_name='event_subscriptions', null=True, blank=True)
    agentInstance = models.ForeignKey("agents.AgentInstance", default=None, on_delete=models.CASCADE, related_name='event_subscriptions', null=True, blank=True)
    eventHandler = models.ForeignKey(EventHandler, default=None, on_delete=models.CASCADE, related_name='event_subscriptions', null=True, blank=True)
    description = models.CharField(default="", help_text="source", max_length=100000)
    ignore_error = models.BooleanField(default=False, help_text="ignore exceptions and errors at runtime")

    def as_client_dict(self):
        receiver_dict = None
        if self.eventHandler:
            receiver_agent_dict = None
            if self.eventHandler.agent:
                receiver_agent_dict = {
                    'pk': self.eventHandler.agent.pk, 
                    'name': self.eventHandler.agent.name
                }
            receiver_dict = {
                'id': self.eventHandler.pk,
                'name': self.eventHandler.name,
                'agent': receiver_agent_dict,
            }

        return {
            'object': 'EventSubscription',
            'id': self.pk,
            'agent': {'pk': self.agent.pk, 'name': self.agent.name} if self.agent else None,
            'agentInstance': {'pk': self.agentInstance.pk} if self.agentInstance else None,
            'eventHandler': receiver_dict,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
            
    def run(self, arguments):
        eventExecution = EventExecution(eventHandler=self.eventHandler, eventSubscription=self, **{f"arg_{k}":v for k,v in arguments.items()})  
        if self.eventHandler.is_blocking:
            eventExecution.run()
            eventExecution.save()
        else:
            eventExecution.save()
            execute_event.delay(eventExecution.pk)    # not celery for now, keep it that way.
    
class EventExecution(BaseModel):
    class EventExecutionStatus(models.TextChoices):
        PENDING = 'PENDING', 'pending execution'
        ACTIVE = 'ACTIVE', 'active'
        FAILED = 'FAILED', 'failed'
        SUCCESS = 'SUCCESS', 'success'

    eventHandler = models.ForeignKey(EventHandler, default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    eventSubscription = models.ForeignKey(EventSubscription, default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    status = models.CharField(max_length=100, choices=EventExecutionStatus.choices, default=EventExecutionStatus.PENDING)

    # arguments the event is called with
    arg_agent = models.ForeignKey(Agent, default=None, on_delete=models.CASCADE, related_name='related_events', null=True, blank=True)
    arg_agentInstance = models.ForeignKey("agents.AgentInstance", default=None, on_delete=models.CASCADE, related_name='related_events', null=True, blank=True)
    arg_conversationMessage = models.ForeignKey("agents.ConversationMessage", default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    arg_llmQuery = models.ForeignKey("agents.LLMQuery", default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    arg_llmResponse = models.ForeignKey("agents.LLMResponse", default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)
    arg_toolCall =  models.ForeignKey("calls.toolCall", default=None, on_delete=models.SET_DEFAULT, related_name='related_events', null=True, blank=True)

    def as_client_dict(self):
        return {
            'object': 'EventSubscription',
            'id': self.pk,
            'eventHandler_id': self.eventHandler_id,
        }

    def run(self):
        env = { 
            "event": self ,
            "ConversationMessage": ConversationMessage,
            "ConversationMessagePart": ConversationMessagePart,
        }
        for arg in ["agent", "agentInstance", "conversationMessage", "llmQuery", "llmResponse", "toolCall"]:
            if value := getattr(self, f"arg_{arg}"): 
                env[arg] = value

        self.status = EventExecution.EventExecutionStatus.ACTIVE
        self.save()
        new_status = EventExecution.EventExecutionStatus.FAILED
        try:
            exec(self.eventHandler.source, env, env)
            new_status = EventExecution.EventExecutionStatus.SUCCESS
        except Exception as e:
            if not self.eventSubscription.ignore_error:
                raise e
        finally:
            self.status = new_status


