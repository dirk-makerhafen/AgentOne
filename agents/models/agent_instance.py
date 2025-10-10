from django.db import models
from django.db.models import Sum
import os

from agents.models.conversation_message import ConversationMessage

from core.models.base_model import BaseModel
from tools.builtin_a2a.a2a_tool import A2ATool
from tools.builtin_a2a.models.a2a_description import AgentToAgentDescription
from tools.builtin_filesystem.filesystem_tool import FilesystemTool
from tools.builtin_memory.memory_tool import MemoryTool
from tools.builtin_memory.prompts import TRACKS
from tools.builtin_python.python_tool import PythonTool
from tools.builtin_shell.shell_tool import ShellTool
from tools.builtin_subscriptions.subscriptions_tool import SubscriptionsTool
from tools.builtin_userinteraction.user_interaction_tool import UserInteractionTool
from tools.instances.mcpclient import MCPClient
from tools.instances.models.tool_instance import ToolInstance
from agents.models.agent_fork import AgentFork
from django.utils import timezone

# Map built-in tool names (as they appear in ToolDefinition.name) to their Python classes.
BUILTIN_TOOL_CLASS_MAP = {
    'filesystem': FilesystemTool,
    'memory': MemoryTool,
    'python': PythonTool,
    'a2a': A2ATool,
    'userinteraction': UserInteractionTool,
    'shell': ShellTool,
    'subscriptions': SubscriptionsTool,
}


class AgentInstance(BaseModel):
    instance_pk = models.AutoField(primary_key=True)
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name ='instances')
    system = models.ForeignKey("systems.System", on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_instances', help_text= 'The system this instance is assigned to run on.')
    aimodel = models.ForeignKey("providers.AiModel", default=None, null=True, on_delete= models.CASCADE, related_name='agent_instances')
    name = models.CharField(max_length=255, default='', blank=True)
    description_text = models.TextField(blank=True, default='', help_text="A description of this specific agent instance.") # New field
    STATUS_CHOICES = [('IDLE', 'Idle'), ('IDLE_AUTOMATED',
        'Idle (Automated)'), ('THINKING', 'Thinking'), ('EXECUTING_TOOLS',
        'Executing Tools'), ('AWAITING_USER_INPUT', 'Awaiting User Input'),
        ('AWAITING_AGENT_MESSAGE', 'Awaiting Agent Message'), ('FINISHED',
        'Finished'), ('ERROR', 'Error'), ('MISCONFIGURED', 'Misconfigured'),
        ('SYSTEM_OFFLINE', 'System Offline')]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='IDLE')
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
        self.tool_instances = {} # Stores instances of actual tool classes (FilesystemTool, MCPClient, etc.)
        self.toolname_to_definition = {} # Maps full_function_name to ToolDefinition object
        # Note: self._setup_tools() is called during instance loading if self.agent is available,
        # or externally after the AgentInstance is fully initialized and associated with an agent.
        # This prevents issues with ForeignKey access during initial object creation.
        self.filesystemTool = FilesystemTool(self) # Keep this for direct access if needed, but tool instances come from _setup_tools
        
        # Initialize toolname_to_class for built-in tools, but do NOT set self.available_tools here.
        # self.available_tools should refer to self.agent.available_tools (the ManyToMany field).
        self.toolname_to_class = {}
        for tool_name, tool_class in BUILTIN_TOOL_CLASS_MAP.items():
            # Create a dummy instance to extract function names
            # Actual instances for agent use are created in _setup_tools
            temp_instance = tool_class(self) 
            for fname in temp_instance.functions.keys():
                self.toolname_to_class[f"{fname}"] = tool_class # Map function name to class, not instance

    @property
    def a2a_description_latest(self): # Renamed property
        latest_log = self.description_logs.order_by('-created_at').first()
        return latest_log.description if latest_log else ''
    
    @a2a_description_latest.setter # Renamed setter
    def a2a_description_latest(self, description, toolCall=None):
        from tools.builtin_a2a.models.a2a_description import AgentToAgentDescription
        d = AgentToAgentDescription(
            agent=self.agent,
            agent_instance=self,
            description=description,
            toolCall=toolCall
        )
        d.save()
        self.send_object_to_clients()

    def get_tool_function(self, full_function_name):
        self._setup_tools()

        # Check built-in tools first
        if full_function_name in self.tool_instances:
            tool_instance_or_client = self.tool_instances[full_function_name]
            # Check if it's a direct callable (built-in tool)
            if hasattr(tool_instance_or_client, 'functions') and full_function_name in tool_instance_or_client.functions:
                tool_def = self.toolname_to_definition[full_function_name]
                return {
                    "arguments": tool_instance_or_client.functions[full_function_name]["parameters"],
                    "callable": getattr(tool_instance_or_client, full_function_name),
                    "tool_definition_id": tool_def.pk
                }

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

    def as_client_dict(self):
        model = self.aimodel or self.agent.aimodel
        model_name = model.name if model else 'N/A'
        model_id = model.pk if model else None

        self._setup_tools()

        all_rule_templates = []
        # Use set() to get unique tool instances, preventing duplicates for tools with multiple functions.
        unique_tool_instances = set(self.tool_instances.values())
        for tool_instance in unique_tool_instances:
            if hasattr(tool_instance, 'get_history_limiting_rules'):
                all_rule_templates.extend(tool_instance.get_history_limiting_rules())

        db_rules = self.history_limiting_rules.filter(is_active=True)
        db_rules_map = {f'{rule.group_name}:{rule.rule_name}': rule for rule in db_rules}
        merged_rules = []
        for template in all_rule_templates:
            group_name = template.get('group_name', 'default')
            rule_name = template['name']
            rule_key = f'{group_name}:{rule_name}'
            rule_data = {
                'group_name': group_name,
                'full_rule_name': rule_key,
                'display_name': rule_name,
                'description': template.get('description', ''),
                'success': template['limits'].get('success'),
                'failed': template['limits'].get('failed'),
                'pending': template['limits'].get('pending'),
                'max': template['limits'].get('max'),
                'db_id': None
            }
            if rule_key in db_rules_map:
                db_rule = db_rules_map[rule_key]
                rule_data['db_id'] = db_rule.pk
                if db_rule.limit_success is not None:
                    rule_data['success'] = db_rule.limit_success
                if db_rule.limit_failed is not None:
                    rule_data['failed'] = db_rule.limit_failed
                if db_rule.limit_pending is not None:
                    rule_data['pending'] = db_rule.limit_pending
                if db_rule.limit_max is not None:
                    rule_data['max'] = db_rule.limit_max
            merged_rules.append(rule_data)

        grouped_rules = {}
        for rule_item in merged_rules:
            group_name = rule_item.pop('group_name', 'default')
            if group_name not in grouped_rules:
                grouped_rules[group_name] = []
            grouped_rules[group_name].append(rule_item)

        for group_name in grouped_rules:
            grouped_rules[group_name].sort(key=lambda x: x['display_name'])

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

    def clone(self):
        from django.db import transaction
        from tools.builtin_memory.models.memory_item import MemoryItem
        from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
        from tools.calls.models.tool_call import ToolCall
        from tools.builtin_python.models.python_tool_var import PythonToolVar
        from tools.builtin_a2a.models.a2a_description import AgentToAgentDescription
        from tools.builtin_memory.prompts import TRACKS

        child_instance = None
        with transaction.atomic():
            child_instance = AgentInstance.objects.create(
                agent=self.agent, system=self.system, aimodel=self.aimodel,
                name=f'Fork of {self.name or f"Instance {self.pk}"}',
                description_text=self.description_text, status='IDLE',
                workingdir=self.workingdir, workingdir_write_allowed=self.workingdir_write_allowed,
                access_rules=self.access_rules,
                limit_max_conversation_messages=self.limit_max_conversation_messages,
                limit_max_memory_items=self.limit_max_memory_items,
                limit_max_automated_steps=self.limit_max_automated_steps
            )

            fork_record = AgentFork.objects.create(
                parent_instance=self, child_instance=child_instance
            )
            fork_time = fork_record.created_at

            # 1. ConversationMessages: Get the latest 'limit' messages to fork.
            parent_messages_to_fork = self.conversationMessages.filter(
                created_at__lt=fork_time
            ).order_by('-created_at')[:self.limit_max_conversation_messages]
            message_ids_to_fork = {msg.id for msg in parent_messages_to_fork}

            # 2. FsLogEntries: Get only the latest version of currently loaded files.
            fs_entries_to_fork = self.fsLogEntries.filter(
                created_at__lt=fork_time, is_newest_version=True
            ).exclude(load_mode=None)

            # 3. ToolCalls: Only fork calls related to the messages being forked.
            tool_calls_to_fork = self.toolCalls.filter(
                created_at__lt=fork_time, conversationMessage_id__in=message_ids_to_fork
            )

            # 4. PythonToolVars: Fork the latest version of each variable.
            python_vars_to_fork = self.python_tool_vars.filter(
                created_at__lt=fork_time, next_version=None
            )

            # 5. AgentToAgentDescription: Fork only the single most recent description.
            description_to_fork = self.description_logs.filter(
                created_at__lt=fork_time
            ).order_by('-created_at').first()

            # 6. MemoryItems: Fork the latest 'limit' items per track and layer.
            memory_items_to_fork = []
            for trackname in TRACKS.keys():
                for layername in TRACKS[trackname]['layers'].keys():
                    items = MemoryItem.objects.filter(
                        agentInstance=self, track=trackname, layer=layername,
                        next_version=None, created_at__lt=fork_time
                    ).order_by('-index')[:self.limit_max_memory_items]
                    memory_items_to_fork.extend(items)

            # Combine all objects to be forked into a single structure
            all_objects_to_fork = {
                ConversationMessage: parent_messages_to_fork,
                FsLogEntry: fs_entries_to_fork,
                ToolCall: tool_calls_to_fork,
                PythonToolVar: python_vars_to_fork,
                MemoryItem: memory_items_to_fork,
            }
            if description_to_fork:
                all_objects_to_fork[AgentToAgentDescription] = [description_to_fork]

            # Process and bulk_create ghost objects for each model type
            for model_class, parent_queryset in all_objects_to_fork.items():
                new_child_objects = []
                for parent_obj in parent_queryset:
                    child_obj = model_class()
                    # Copy fields
                    for field in parent_obj._meta.fields:
                        if not field.primary_key and field.name not in ['id', 'pk', 'agentinstance', 'agent_instance']:
                            setattr(child_obj, field.name, getattr(parent_obj, field.name))

                    child_obj.agentInstance = child_instance
                    child_obj.fork_of = parent_obj
                    child_obj.raw_data_reference = parent_obj
                    new_child_objects.append(child_obj)

                if new_child_objects:
                    model_class.objects.bulk_create(new_child_objects)

        return child_instance

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
        if self.status in ['THINKING', 'EXECUTING_TOOLS']:
            return
        self.status = 'THINKING'
        self.require_user_interaction = False
        self.save()
        if self.system and self.system.status != 'online':
            print(f"AgentInstance {self.instance_pk} is assigned to system '{self.system.name}' which is not online. Cannot start.")
            self.status = 'SYSTEM_OFFLINE'
            self.save()
            return
        celery_create_query.apply_async(args=[self.instance_pk])
        
    def _setup_tools(self):
        # This method discovers available tools (both built-in and running external tools)
        # and prepares client instances for them.

        self.tool_instances = {}
        self.toolname_to_definition = {}

        from tools.definitions.models.tool_definition import ToolDefinition
        
        # 1. Load all built-in tools
        for tool_name, tool_class in BUILTIN_TOOL_CLASS_MAP.items():
            try:
                instance = tool_class(self)
                tool_def = ToolDefinition.objects.get(name=tool_name, is_builtin=True)
                for func_name in instance.functions:
                    self.tool_instances[func_name] = instance
                    self.toolname_to_definition[func_name] = tool_def
            except ToolDefinition.DoesNotExist:
                print(f"Error: Built-in ToolDefinition '{tool_name}' not found.")
            except Exception as e:
                print(f"Error initializing built-in tool {tool_name}: {e}")

        # 2. Discover running external (MCP) tools
        if not (self.agent and self.system):
            return # Cannot discover external tools without an agent and an assigned system.

        from tools.definitions.models.tool_installation import ToolInstallation
        for tool_def in self.agent.available_tools.filter(is_builtin=False):
            installation = None
            if tool_def.execution_mode == ToolDefinition.ExecutionMode.SHARED:
                installation = self.system.tool_installations.filter(
                    tool_definition=tool_def,
                    agent_instance__isnull=True
                ).first()
            elif tool_def.execution_mode == ToolDefinition.ExecutionMode.DEDICATED:
                installation = self.system.tool_installations.filter(
                    tool_definition=tool_def,
                    agent_instance=self
                ).first()

            # Find all running instances for this installation
            running_instances = installation.instances.filter(status=ToolInstance.Status.RUNNING)
            if not running_instances.exists():
                continue

            # For now, we connect to the most recently started running instance.
            # A future enhancement could involve load balancing or round-robin.
            latest_running_instance = running_instances.order_by('-created_at').first()

            try:
                # The MCPClient is the object that knows how to communicate with the tool
                client = MCPClient(tool_instance=latest_running_instance)
                self.tool_instances[tool_def.name] = client
                self.toolname_to_definition[tool_def.name] = tool_def
                print(f"Connected to running tool '{tool_def.name}' via instance {latest_running_instance.pk}.")
            except Exception as e:
                print(f"Error creating MCPClient for tool '{tool_def.name}': {e}")
            
    def delete(self, *args, **kwargs):
        from django.contrib.auth.models import User
        from core.tasks.send_websocket_update import celery_send_websocket_update

        instance_pk_to_broadcast = self.instance_pk
        agent_pk_to_broadcast = self.agent.agent_pk # Also send parent agent_pk for sidebar updates

        super().delete(*args, **kwargs)

        # After deletion, broadcast the update to all users
        message_data = {
            'object': 'AgentInstanceDeleted',
            'instance_pk': instance_pk_to_broadcast,
            'agent_pk': agent_pk_to_broadcast # Include agent_pk for efficient UI updates in SidebarAgents
        }
        all_user_pks = User.objects.values_list('pk', flat=True)
        for pk in all_user_pks:
            celery_send_websocket_update.delay(message_data, user_pk=pk)

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
        print("result", combined_messages)
        return combined_messages
