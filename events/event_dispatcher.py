
import traceback

from celery import group
from agents.models.debug_log_entry import DebugLogEntry
from events.models.event_execution import EventExecution
from events.models.event_handler import EventHandler
from events.models.event_subscription import EventSubscription, ExecutionMode
from django.db.models import Q

from events.models.event_type import EventTypes
from events.tasks import execute_event


class EventDispatcher():     
    @classmethod
    def event_agentinstance_created(cls, agent, agentInstance):
        cls._run_handlers(eventType = EventTypes.agentinstance_created, agent = agent, agentInstance = agentInstance)   
    
    @classmethod
    def event_conversationMessage_added(cls, agent, agentInstance, conversationMessage):
        cls._run_handlers(EventTypes.conversationMessage_added, agent = agent, agentInstance = agentInstance, conversationMessage = conversationMessage)   
    

    # LLM QUERY
    @classmethod
    def event_llmquery_pre_create(cls, agent, agentInstance):
        cls._run_handlers(EventTypes.llmquery_pre_create, agent = agent, agentInstance = agentInstance, )   
    
    @classmethod
    def event_llmquery_post_create(cls, agent, agentInstance, llmQuery):
        cls._run_handlers(EventTypes.llmquery_post_create, agent = agent, agentInstance = agentInstance, llmQuery = llmQuery)   
    
    @classmethod
    def event_llmquery_pre_execute(cls, agent, agentInstance, llmQuery):
        cls._run_handlers(EventTypes.llmquery_pre_execute, agent = agent, agentInstance = agentInstance, llmQuery = llmQuery)   
    
    @classmethod
    def event_llmquery_post_execute(cls, agent, agentInstance, llmQuery):
        cls._run_handlers(EventTypes.llmquery_post_execute, agent = agent, agentInstance = agentInstance, llmQuery = llmQuery)   
    
    @classmethod
    def event_llmquery_successfull(cls, agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_handlers(EventTypes.llmquery_successfull, agent = agent, agentInstance = agentInstance, llmQuery = llmQuery, llmResponse = llmResponse, conversationMessage = conversationMessage)   
    
    @classmethod
    def event_llmquery_failed(cls, agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_handlers(EventTypes.llmquery_failed, agent = agent, agentInstance = agentInstance, llmQuery = llmQuery, llmResponse = llmResponse, conversationMessage = conversationMessage)   
    

    # LLM RESPONSE
    @classmethod
    def event_llmresponse_pre_parse(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_handlers(EventTypes.llmresponse_pre_parse, agent = agent, agentInstance = agentInstance, llmQuery = llmQuery, llmResponse = llmResponse, conversationMessage = conversationMessage)   
    
    @classmethod
    def event_llmresponse_post_parse(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_handlers(EventTypes.llmresponse_post_parse, agent = agent, agentInstance = agentInstance, llmQuery = llmQuery, llmResponse = llmResponse, conversationMessage = conversationMessage)   
    
    @classmethod
    def event_llmresponse_pre_tool_calls(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_handlers(EventTypes.llmresponse_pre_tool_calls, agent = agent, agentInstance = agentInstance, llmQuery = llmQuery, llmResponse = llmResponse, conversationMessage = conversationMessage)   
    
    @classmethod
    def event_llmresponse_pre_tool_call(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage, toolCall):
        cls._run_handlers(EventTypes.llmresponse_pre_tool_call, agent = agent, agentInstance = agentInstance, llmQuery = llmQuery, llmResponse = llmResponse, conversationMessage = conversationMessage, toolCall = toolCall)   
    
    @classmethod
    def event_llmresponse_post_tool_call(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage, toolCall):
        cls._run_handlers(EventTypes.llmresponse_post_tool_call, agent = agent, agentInstance = agentInstance, llmQuery = llmQuery, llmResponse = llmResponse, conversationMessage = conversationMessage, toolCall = toolCall)   
    
    @classmethod
    def event_llmresponse_post_tool_calls(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_handlers(EventTypes.llmresponse_post_tool_calls, agent = agent, agentInstance = agentInstance, llmQuery = llmQuery, llmResponse = llmResponse, conversationMessage = conversationMessage)   
    
    @classmethod
    def event_llmresponse_finished(cls,  agent, agentInstance, llmQuery, llmResponse, conversationMessage):
        cls._run_handlers(EventTypes.llmresponse_finished, agent = agent, agentInstance = agentInstance,  llmQuery = llmQuery, llmResponse = llmResponse, conversationMessage = conversationMessage)   


    # AGENT TASK EVENTS
    @classmethod
    def event_agenttask_added(cls,  agent, agentInstance, agentTask):
        cls._run_handlers(EventTypes.agenttask_added, agent = agent, agentInstance = agentInstance,  agentTask = agentTask)   
    
    @classmethod
    def event_agenttask_activated(cls,  agent, agentInstance, agentTask):
        cls._run_handlers(EventTypes.agenttask_activated, agent = agent, agentInstance = agentInstance,  agentTask = agentTask)   
    
    @classmethod
    def event_agenttask_pre_finish(cls,  agent, agentInstance, agentTask):
        cls._run_handlers(EventTypes.agenttask_pre_finish, agent = agent, agentInstance = agentInstance,  agentTask = agentTask)   

    @classmethod
    def event_agenttask_finished(cls,  agent, agentInstance, agentTask):
        cls._run_handlers(EventTypes.agenttask_finished, agent = agent, agentInstance = agentInstance,  agentTask = agentTask)   

    @classmethod
    def event_agenttask_children_finished(cls,  agent, agentInstance, agentChildTasks):
        cls._run_handlers(EventTypes.agenttask_children_finished, agent = agent, agentInstance = agentInstance,  agentChildTasks = agentChildTasks)   




    @classmethod 
    def _run_handlers(cls, event, agent, agentInstance, agentChildTasks=None, **kwargs):
        eventSubscriptions = EventSubscription.objects.filter(Q(emitter_agent=agent) | Q(emitter_agentInstance=agentInstance), eventHandler__event=event.name, eventHandler__enabled=True)
        parallel_eventExecutions = []
        sequential_eventExecutions = []
        for eventSubscription in eventSubscriptions:
            eventExecution = EventExecution.objects.create(
                eventSubscription = eventSubscription, 
                eventHandler = eventSubscription.eventHandler, 
                agent = agent,
                agentInstance = agentInstance,
                **kwargs
            )
            if agentChildTasks:
                eventExecution.agentChildTasks.set(agentChildTasks)

            if eventSubscription.execution_mode == ExecutionMode.BLOCKING:
                sequential_eventExecutions.append(eventExecution)
            elif eventSubscription.execution_mode == ExecutionMode.PARALLEL:
                parallel_eventExecutions.append(eventExecution)
            elif eventSubscription.execution_mode == ExecutionMode.DETACHED:
                execute_event.delay(eventExecution.pk)
        
        if parallel_eventExecutions:
            parallel = group([execute_event.s(eventExecution.pk) for eventExecution in parallel_eventExecutions])()
        
        for sequential_eventExecution in sequential_eventExecutions:
            try:
                sequential_eventExecution.run()
            except Exception as e:
                DebugLogEntry.objects.create(agentInstance=agentInstance, event = 'exception', data = {"message": f"Error running event Execution {sequential_eventExecution}", "exception": f'{e}\n{traceback.format_exc()}'})
                raise e

        if parallel_eventExecutions:
            results = parallel.get()   # blocks

