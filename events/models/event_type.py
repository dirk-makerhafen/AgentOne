
from enum import Enum
from django.db import models

class EventType(models.Model):
    name = models.CharField(max_length=50, primary_key=True)
    description = models.TextField(default="", max_length=64000, blank=True)

    def __str__(self):
        return self.name
    
class EventTypes(Enum):
    agentinstance_created       = 'agentinstance_created'       , 'agentinstance_created        (agent, agentInstance)'

    agenttask_added      = 'agenttask_added'      , 'agenttask_added     (agent, agentInstance, agentTask)'
    agenttask_activated  = 'agenttask_activated'  , 'agenttask_activated (agent, agentInstance, agentTask)'
    agenttask_pre_finish = 'agenttask_pre_finish' , 'agenttask_pre_finish       (agent, agentInstance, agentTask)'
    agenttask_finished   = 'agenttask_finished'   , 'agenttask_finished  (agent, agentInstance, agentTask)'
    agenttask_children_finished = 'agenttask_children_finished'   , 'agenttask_children_finished  (agent, agentInstance, agentChildTasks)'
    conversationMessage_added   = 'conversationMessage_added'   , 'conversationMessage_added    (agent, agentInstance, conversationMessage)'

    llmquery_pre_create         = 'llmquery_pre_create'         , 'llmquery_pre_create          (agent, agentInstance)'
    llmquery_post_create        = 'llmquery_post_create'        , 'llmquery_post_create         (agent, agentInstance, llmQuery)'
    llmquery_pre_execute        = 'llmquery_pre_execute'        , 'llmquery_pre_execute         (agent, agentInstance, llmQuery)'
    llmquery_post_execute       = 'llmquery_post_execute'       , 'llmquery_post_execute         (agent, agentInstance, llmQuery, llmResponse, conversationMessage)'
    
    #toolcall_pre_execute   = 'llmresponse_pre_tool_call'   , 'llmresponse_pre_tool_call    (agent, agentInstance, toolcall)'
    toolcall_post_execute  = 'llmresponse_post_tool_call'  , 'llmresponse_post_tool_call   (agent, agentInstance, toolcall)'
    
    def instance(self):
        return EventType.objects.get(name=self.value[0])
