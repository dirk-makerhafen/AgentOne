from django.db import models
from django.db.models import Sum
import random

from jinja2 import BaseLoader, Environment
from agents.history_limiter import HistoryLimiter
from agents.models.agent_task import AgentTask
from agents.models.conversation_message import ConversationMessage, ConversationMessagePart
from core.models.base_model import BaseModel
from core.models.prompt import Prompt
from systems.models.system import System
from tools.base.buildin_tools_map import BUILTIN_TOOL_CLASS_MAP
from django.utils import timezone
from django.db.models import Q
import re





class AgentInstance(BaseModel):
    class AgentInstanceStatusChoices(models.TextChoices):
        IDLE = 'IDLE', 'Idle'
        PROCESSING_MESSAGE = 'PROCESSING_MESSAGE', 'Processing Message'

        QUERY_CREATE = 'QUERY_CREATE', 'QUERY_CREATE'
        QUERY_PENDING = 'QUERY_PENDING', 'QUERY_PENDING'
        QUERY_COMPILE = 'QUERY_COMPILE', 'QUERY_COMPILE'
        QUERY_ACTIVE = 'QUERY_ACTIVE', 'QUERY_ACTIVE'

        RESPONSE_PROCESS = 'RESPONSE_PROCESS', 'RESPONSE_PROCESS'

        TOOLCALLS_PENDING = 'TOOLCALLS_PENDING', 'TOOLCALLS_PENDING'
        TOOLCALLS_ACTIVE = 'TOOLCALLS_ACTIVE', 'TOOLCALLS_ACTIVE'

        AWAITING_USER_INPUT = 'AWAITING_USER_INPUT', 'Awaiting User Input'

        ERROR = 'ERROR', 'Error'
        SYSTEM_OFFLINE = 'SYSTEM_OFFLINE', 'System Offline'


    instance_pk = models.AutoField(primary_key=True)
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name ='instances')
    system = models.ForeignKey("systems.System", on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_instances', help_text= 'The system this instance is assigned to run on.')
    aimodel = models.ForeignKey("providers.AiModel", blank=True, default=None, null=True, on_delete= models.CASCADE, related_name='agent_instances')
    name = models.CharField(max_length=255, default='', blank=True)
    description_text = models.TextField(blank=True, default='', help_text="A description of this specific agent instance.") # New field
    status = models.CharField(max_length=30, choices=AgentInstanceStatusChoices.choices, default=AgentInstanceStatusChoices.IDLE)
    workingdir = models.CharField(max_length=1024, default='')
    require_user_interaction = models.BooleanField(default=False)
    limit_max_conversation_messages = models.IntegerField(default=None, null=True, blank=True, help_text="Override the agent's default maximum number of messages in conversation history send in llm requests.")
    limit_max_new_conversation_messages= models.IntegerField(default=None, null=True, blank=True, help_text="Override the agent's default maximum number of new messages in conversation history send in llm requests.")
    limit_max_memory_items = models.IntegerField(default=None, null=True, blank=True, help_text="Override the agent's default maximum number of items in memory.")
    limit_max_automated_steps = models.IntegerField(default=None, null=True, blank=True, help_text="Override the agent's default maximum number of automated steps.")
    automated_step_count = models.IntegerField(default=0)
    workingdir_write_allowed = models.BooleanField(default=True, help_text ='Allow write operations within the working directory.')
    access_rules = models.TextField(blank=True, default='', help_text= "Fine-grained access rules, one per line. E.g., '!path/to/deny', '>path/to/allow', '</path/to/readonly'.")
    max_requests_per_minute = models.IntegerField(default=None, null=True, blank=True, help_text="Maximum requests per minute for this instance or its subtree. Null means inheriting from parent.")
    max_token_per_minute = models.IntegerField(default=None, null=True, blank=True, help_text="Maximum tokens per minute for this instance or its subtree. Null means inheriting from parent.")
    parent = models.ForeignKey("agents.AgentInstance",  default=None, null=True, blank=True, on_delete=models.CASCADE, related_name='children')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._filesystem = None

    @property
    def current_aimodel(self):
        return self.aimodel if self.aimodel is not None else self.agent.aimodel
    
    @property
    def filesystem(self):
        if not self._filesystem:
            self._filesystem = BUILTIN_TOOL_CLASS_MAP["filesystem"](self)
        return self._filesystem

    @property
    def effective_limit_max_conversation_messages(self):
        return self.limit_max_conversation_messages if self.limit_max_conversation_messages is not None else self.agent.limit_max_conversation_messages
    
    @property
    def effective_limit_max_new_conversation_messages(self):
        return self.limit_max_new_conversation_messages if self.limit_max_new_conversation_messages is not None else self.agent.limit_max_new_conversation_messages

    @property
    def effective_limit_max_memory_items(self):
        return self.limit_max_memory_items if self.limit_max_memory_items is not None else self.agent.limit_max_memory_items

    @property
    def effective_limit_max_automated_steps(self):
        return self.limit_max_automated_steps if self.limit_max_automated_steps is not None else self.agent.limit_max_automated_steps

    @property
    def effective_max_requests_per_minute(self):
        if self.max_requests_per_minute is not None:
            return self.pk, self.max_requests_per_minute
        if hasattr(self, 'fork_origin') and self.fork_origin:
            return self.fork_origin.parent_instance.effective_max_requests_per_minute
        if hasattr(self, 'supervisor_link') and self.supervisor_link:
            return self.supervisor_link.supervisor_instance.effective_max_requests_per_minute
        return None # No explicit limit found up the hierarchy

    @property
    def effective_max_token_per_minute(self):
        if self.max_token_per_minute is not None:
            return self.pk, self.max_token_per_minute
        if hasattr(self, 'fork_origin') and self.fork_origin:
            return self.fork_origin.parent_instance.effective_max_token_per_minute
        if hasattr(self, 'supervisor_link') and self.supervisor_link:
            return self.supervisor_link.supervisor_instance.effective_max_token_per_minute
    
        return None # No explicit limit found up the hierarchy

    def set_workingdir(self, workingdir):
        if workingdir != self.workingdir:
            loaded_items = self.filesystem.get_loaded_items()
            for loaded_item in loaded_items:
                self.filesystem.fs_unload(path=loaded_item.path, toolCall=None)
            self.workingdir = workingdir
            AgentInstance.objects.filter(instance_pk=self.instance_pk).update(workingdir=workingdir)
            self.send_object_to_clients()

    def set_status(self, status):
        self.status = status
        if AgentInstance.objects.filter(~Q(status=status), instance_pk=self.instance_pk).update(status=status):
            self.send_object_to_clients()

    def set_automated_step_count(self, steps):
        self.automated_step_count = steps
        if AgentInstance.objects.filter(~Q(automated_step_count=steps), instance_pk=self.instance_pk).update(automated_step_count=steps):
            self.send_object_to_clients()

    def _split_injected_messages(self, parts):
        print("_split_injected_messages", parts)
        new_parts = []
        INJECT_RE = re.compile(r"""!(IMAGE|FILE):("(?:[^"\\]|\\.)*" | '(?:[^'\\]|\\.)*' | (?:[^\s'"]|\\ )+)""", re.VERBOSE)
        for p in parts:
            if p["type"] != "TEXT":
                new_parts.append(p) # FILE or IMAGE part already parsed — pass through unchanged
            else:
                last = 0
                for match in INJECT_RE.finditer(p["content"]):
                    start, end = match.span()
                    typ, raw_path = match.groups()
                    if start > last: # text before the injection
                        new_parts.append({"type": "TEXT", "content": p["content"][last:start]})
                    path = bytes(raw_path.strip('"\'').replace("\\ ", " "), "utf8").decode("unicode_escape") # normalize the path
                    new_parts.append({"type": typ, "content": f"path:{path}"})
                    last = end
                if last < len(p["content"]): # tail text
                    new_parts.append({"type": "TEXT", "content": p["content"][last:]})
        print("NEW PARTS:", new_parts)
        return new_parts

    def add_to_conversation(self, role, parts=None, message=None, trigger_query= False, is_human_input=False):
        from events.event_dispatcher import EventDispatcher
        from agents.tasks.create_query import celery_create_query

        if parts is None and message is not None:
            parts = [{"content": message, "type": "TEXT"}]
        parts = self._split_injected_messages(parts)

        is_our_process = False
        if is_human_input:
            if self.require_user_interaction:
                self.require_user_interaction = False
            if self.status in [ AgentInstance.AgentInstanceStatusChoices.AWAITING_USER_INPUT,  AgentInstance.AgentInstanceStatusChoices.ERROR]:
                self.set_status(AgentInstance.AgentInstanceStatusChoices.PROCESSING_MESSAGE)
                is_our_process = True
            self.set_automated_step_count(0)

        if self.status == AgentInstance.AgentInstanceStatusChoices.IDLE:
            self.set_status(AgentInstance.AgentInstanceStatusChoices.PROCESSING_MESSAGE)
            is_our_process = True

        conversationMessage= None
        conversationMessage = ConversationMessage.objects.create(role = role, agent = self.agent, agentInstance = self, trigger_query = trigger_query)
        for part in parts:
            ConversationMessagePart.objects.create(content = part["content"], content_type = part["type"], conversationMessage = conversationMessage)
        EventDispatcher.event_conversationMessage_added(self.agent, self, conversationMessage)
        conversationMessage.refresh_from_db()
        if not parts:
            if self.status in [  AgentInstance.AgentInstanceStatusChoices.IDLE, AgentInstance.AgentInstanceStatusChoices.PROCESSING_MESSAGE]:
                self.process_next_task()

        self.refresh_from_db()
        if (not conversationMessage and trigger_query is True) or conversationMessage.trigger_query is True:
            celery_create_query.delay(self.instance_pk)
        else:
            self.set_status(AgentInstance.AgentInstanceStatusChoices.IDLE)
        return conversationMessage
    
    def add_task(self, arguments=None, status=AgentTask.AgentInstanceTaskStatusChoices.PENDING, group=None, parent_task=None ):
        new_task = AgentTask.objects.create(agent=self.agent, agentInstance = self, arguments=arguments, status=status, group=group, parent=parent_task)
        if self.status == AgentInstance.AgentInstanceStatusChoices.IDLE:
            self.process_next_task()

    def process_next_task(self):
        from events.event_dispatcher import EventDispatcher
        if self.status != AgentInstance.AgentInstanceStatusChoices.IDLE and  self.status != AgentInstance.AgentInstanceStatusChoices.PROCESSING_MESSAGE  :
            raise Exception(f"status if agentInstance:{self.pk} must be idle or idle automated to process next task but is {self.status}")
        current_task = self.get_active_task()
        if current_task:
            raise Exception(f"Some task is already active {current_task}")
        next_task = self.get_next_pending_task()
        if not next_task:
            self.set_status(AgentInstance.AgentInstanceStatusChoices.IDLE)
            return 
        next_task.status = "ACTIVE"
        next_task.save()
        EventDispatcher.event_agenttask_activated(self.agent, self, next_task)
        print("NEXT TASK", next_task, next_task.data)
        p = Prompt.get_template(key="task", source="Agent", agentInstance=self, agent=self.agent)
        rtemplate = Environment(loader=BaseLoader).from_string(p.value)                
        part_content = rtemplate.render({"task": next_task})
        print("GOT FROM TASK", part_content)
        self.add_to_conversation(role="user", message=part_content, trigger_query=True)

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

        pinned_messages = self.conversationMessages.filter( pin_to_context=True).order_by('created_at').all()
        recent_nonpinned_messages_query = self.conversationMessages.filter(pin_to_context=False, created_at__lt=max_timestamp).order_by('-created_at')
        if max_id:
            recent_nonpinned_messages_query = recent_nonpinned_messages_query.filter(id__lt=max_id)        
        recent_nonpinned_messages = recent_nonpinned_messages_query.all()[:limit]
        combined_messages = list(pinned_messages) + list(recent_nonpinned_messages)
        if len(combined_messages) < limit: # need more messages
            missing_cnt = limit - len(combined_messages) 
            if hasattr(self, 'fork_origin') and self.fork_origin:  # has fork, use for messages
                combined_messages.extend(self.fork_origin.parent_instance.get_conversation_messages(limit=missing_cnt, max_timestamp = self.fork_origin.created_at))
        return combined_messages
      
    def get_active_task(self):
        return self.tasks.filter(status="ACTIVE").first()

    def get_next_pending_task(self):
        return self.tasks.filter(status="PENDING").first()

    def as_client_dict(self):
        model = self.current_aimodel
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
            'default_limit_max_conversation_messages': self.agent.limit_max_conversation_messages,
            'default_limit_max_memory_items': self.agent.limit_max_memory_items,
            'default_limit_max_automated_steps': self.agent.limit_max_automated_steps,
            'effective_limit_max_conversation_messages': self.effective_limit_max_conversation_messages,
            'effective_limit_max_memory_items': self.effective_limit_max_memory_items,
            'effective_limit_max_automated_steps': self.effective_limit_max_automated_steps,
            'automated_step_count': self.automated_step_count,
            'workingdir_write_allowed': self.workingdir_write_allowed,
            'access_rules': self.access_rules,
            'history_limiting_rules': grouped_rules,
            'total_prompt_tokens': total_prompt,
            'total_completion_tokens': total_completion,
            'max_requests_per_minute': self.max_requests_per_minute,
            'max_token_per_minute': self.max_token_per_minute
        }

    def __str__(self):
            return f'Instance:{self.instance_pk}:{self.name} Agent:{self.agent.name}:{self.agent.pk}:'
    