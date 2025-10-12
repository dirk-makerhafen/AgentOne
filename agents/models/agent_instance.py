from django.db import models
from django.db.models import Sum

from agents.history_limiter import HistoryLimiter
from agents.models.conversation_message import ConversationMessage
from core.models.base_model import BaseModel
from systems.models.system import System
from tools.base.buildin_tools_map import BUILTIN_TOOL_CLASS_MAP
from tools.instances.mcpclient import MCPClient
from django.utils import timezone

class AgentInstance(BaseModel):
    class AgentInstanceStatusChoices(models.TextChoices):
        IDLE = 'IDLE', 'Idle'
        IDLE_AUTOMATED = 'IDLE_AUTOMATED', 'Idle (Automated)'
        THINKING = 'THINKING', 'Thinking'
        EXECUTING_TOOLS = 'EXECUTING_TOOLS', 'Executing Tools'
        AWAITING_USER_INPUT = 'AWAITING_USER_INPUT', 'Awaiting User Input'
        AWAITING_AGENT_MESSAGE = 'AWAITING_AGENT_MESSAGE', 'Awaiting Agent Message'
        FINISHED = 'FINISHED','Finished'
        ERROR = 'ERROR', 'Error'
        SYSTEM_OFFLINE = 'SYSTEM_OFFLINE', 'System Offline'

    instance_pk = models.AutoField(primary_key=True)
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name ='instances')
    system = models.ForeignKey("systems.System", on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_instances', help_text= 'The system this instance is assigned to run on.')
    aimodel = models.ForeignKey("providers.AiModel", default=None, null=True, on_delete= models.CASCADE, related_name='agent_instances')
    name = models.CharField(max_length=255, default='', blank=True)
    description_text = models.TextField(blank=True, default='', help_text="A description of this specific agent instance.") # New field
    status = models.CharField(max_length=30, choices=AgentInstanceStatusChoices.choices, default=AgentInstanceStatusChoices.IDLE)
    workingdir = models.CharField(max_length=1024, default='')
    require_user_interaction = models.BooleanField(default=False)
    limit_max_conversation_messages = models.IntegerField(default=20)
    limit_max_memory_items = models.IntegerField(default=15)
    limit_max_automated_steps = models.IntegerField(default=0)
    automated_step_count = models.IntegerField(default=0)
    workingdir_write_allowed = models.BooleanField(default=False, help_text ='Allow write operations within the working directory.')
    access_rules = models.TextField(blank=True, default='', help_text= "Fine-grained access rules, one per line. E.g., '!path/to/deny', '>path/to/allow', '</path/to/readonly'.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filesystem = None

    @property
    def filesystem(self):
        if not self._filesystem:
            self._filesystem = BUILTIN_TOOL_CLASS_MAP["filesystem"](self)
        return self._filesystem

    @property
    def available_tools(self):
        return self.agent.available_tools

    def get_tool_function(self, full_function_name):
        for toolDefinition in self.agent.available_tools.all():
            if toolDefinition.is_builtin:
                buildin_tool_class = BUILTIN_TOOL_CLASS_MAP[toolDefinition.name]
                if full_function_name in buildin_tool_class.functions:
                    buildin_tool_instance = buildin_tool_class(self)
                    return {
                        "arguments": buildin_tool_class.functions[full_function_name]["parameters"],
                        "callable": getattr(buildin_tool_instance, full_function_name),
                        "tool_definition_id": toolDefinition.pk
                    }
            else:
                print("NONE BUILDON")

                # Check for external MCP tools (e.g., 'my-tool.do_something')
                if '.' in full_function_name:
                    tool_name, method_name = full_function_name.split('.', 1)
                    if tool_name in self.tool_instances:
                        mcp_client = self.tool_instances[tool_name]
                        tool_def = self.toolname_to_definition[tool_name]
                        if isinstance(mcp_client, MCPClient):
                            # The schema for the method's arguments should be fetched from the tool.
                            # For now, we assume a generic dict. A future improvement would be to
                            # have mcp_client.get_method_schema(method_name).
                            return {
                                "arguments": {"type": "object", "properties": {}},
                                "callable": lambda **kwargs: mcp_client.invoke_tool(method_name, kwargs),
                                "tool_definition_id": tool_def.pk
                            }

        raise ValueError(f"Tool function '{full_function_name}' not found or not enabled for this agent instance.")

    def add_to_conversation(self, role, content):
        c = ConversationMessage()
        c.agent = self.agent
        c.agentInstance = self
        c.role = role
        c.data = {'parts': [{'content': content}]}
        c.save()
        return c

    def start_or_continue(self):
        from agents.tasks.create_query import celery_create_query
        if self.status in [AgentInstance.AgentInstanceStatusChoices.THINKING, AgentInstance.AgentInstanceStatusChoices.EXECUTING_TOOLS]:
            return
        self.status =  AgentInstance.AgentInstanceStatusChoices.THINKING
        self.require_user_interaction = False
        self.save()
        if self.system and self.system.status != System.SystemStatusChoices.ONLINE:
            self.status = AgentInstance.AgentInstanceStatusChoices.SYSTEM_OFFLINE
            self.save()
            return
        celery_create_query.delay(self.instance_pk)
        
    def get_delete_broadcast_payload(self):
        return {
            'object': 'AgentInstanceDeleted',
            'instance_pk': self.instance_pk,
            'agent_pk': self.agent.agent_pk
        }

    def get_conversation_messages(self, limit=None, max_timestamp=None, max_id=None):
        """
        Retrieves conversation messages for this instance. Thanks to the new
        forking model, this is now a simple query on the instance's own
        related messages, as forked messages are copied as "ghost" objects.
        """
        if limit is None:
            limit = self.limit_max_conversation_messages
        if max_timestamp==None:
            max_timestamp = timezone.datetime.max

        pinned_messages = self.conversationMessages.filter(hide_from_context=False, pin_to_context=True).order_by('created_at').all()
        recent_nonpinned_messages_query = self.conversationMessages.filter(hide_from_context=False, pin_to_context=False, created_at__lt=max_timestamp).order_by('-created_at')
        if max_id:
            recent_nonpinned_messages_query = recent_nonpinned_messages_query.filter(id__lt=max_id)        
        recent_nonpinned_messages = recent_nonpinned_messages_query.all()[:limit]
        combined_messages = list(pinned_messages) + list(recent_nonpinned_messages)
        if len(combined_messages) < limit: # need more messages
            missing_cnt = limit - len(combined_messages) 
            if hasattr(self, 'fork_origin') and self.fork_origin:  # has fork, use for messages
                combined_messages.extend(self.fork_origin.parent_instance.get_conversation_messages(limit=missing_cnt, max_timestamp = self.fork_origin.created_at))
        return combined_messages
      
    def as_client_dict(self):
        model = self.aimodel or self.agent.aimodel
        model_name = model.name if model else 'N/A'
        model_id = model.pk if model else None
        history_limiter = HistoryLimiter(self)
        grouped_rules = history_limiter.get_merged_history_limiting_rules()

        token_totals = self.llmResponses.aggregate(total_prompt_tokens=Sum('prompt_tokens'), total_completion_tokens=Sum('completion_tokens'))
        total_prompt = token_totals.get('total_prompt_tokens') or 0
        total_completion = token_totals.get('total_completion_tokens') or 0

        return {
            'object': 'AgentInstance',
            'id': self.pk,
            'agent_id': self.agent.agent_pk,
            'created_at': self.created_at.isoformat(),
            'name': self.name,
            'description_text': self.description_text, # Use the new description_text field
            'status': self.status,
            'status_display': self.get_status_display(),
            'agent_name': self.agent.name,
            'agent_description': self.agent.description,
            'model_name': model_name,
            'model_id': model_id,
            'system_name': self.system.name if self.system else 'Unassigned',
            'system_id': self.system.pk if self.system else None,
            'workingdir': self.workingdir,
            'limit_max_conversation_messages': self.limit_max_conversation_messages,
            'limit_max_memory_items': self.limit_max_memory_items,
            'limit_max_automated_steps': self.limit_max_automated_steps,
            'automated_step_count': self.automated_step_count,
            'workingdir_write_allowed': self.workingdir_write_allowed,
            'access_rules': self.access_rules,
            'history_limiting_rules': grouped_rules,
            'total_prompt_tokens': total_prompt,
            'total_completion_tokens': total_completion
        }

    def __str__(self):
            return f'Instance {self.instance_pk} of Agent {self.agent.name}'

