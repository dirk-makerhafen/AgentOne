from django.db import models
from agent.models.conversation import ConversationMessage
from common.models import ModelWithJsonData
from tools_filesystem.filesystem import FilesystemTool
from tools_memory.memory import SMLMemoryTool
from tools_python.pythontool import PythonTool
from tools_a2a.tool import A2ATool
from tools_userinteraction.tool import UserInteractionTool
from tools_shell.shelltool import ShellTool
from tools_subscriptions.tool import SubscriptionsTool
from tools_a2a.models import AgentInstanceDescriptionLog
import os
from django.db.models import Q, Sum
from providers.models import Model
from django.contrib.auth.models import User
from systems.models import System
from tools_common.models  import ToolDefinition
from agent.mcpclient import MCPClient

# Map built-in tool names (as they appear in ToolDefinition.name) to their Python classes.
BUILTIN_TOOL_CLASS_MAP = {
    'filesystem': FilesystemTool,
    'memory': SMLMemoryTool,
    'python': PythonTool,
    'a2a': A2ATool,
    'userinteraction': UserInteractionTool,
    'shell': ShellTool,
    'subscriptions': SubscriptionsTool,
}



class Agent(ModelWithJsonData):
    agent_pk = models.AutoField(primary_key=True)
    owners = models.ManyToManyField(User, related_name='owned_agents', blank=True)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    model = models.ForeignKey(Model, default=None, on_delete=models.CASCADE, related_name='agents', null=True)
    available_tools = models.ManyToManyField(ToolDefinition, related_name='agents_using_this_tool', blank=True)

    def __str__(self):
        return f'Agent: {self.name}'

    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            from dashboard.tasks import send_object_to_clients
            send_object_to_clients(self)

    def as_client_dict(self):
        return {
            'object': 'Agent', 
            'id': self.agent_pk, 
            'created_at': self.created_at.isoformat(), 
            'name': self.name, 
            'description': self.description
        }

class AgentInstance(ModelWithJsonData):
    instance_pk = models.AutoField(primary_key=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name ='instances')
    system = models.ForeignKey(System, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_instances', help_text= 'The system this instance is assigned to run on.')
    model = models.ForeignKey(Model, default=None, null=True, on_delete= models.CASCADE, related_name='agent_instances')
    name = models.CharField(max_length=255, default='', blank=True)
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
    def description(self):
        latest_log = self.description_logs.order_by('-created_at').first()
        return latest_log.description if latest_log else ''
    
    @description.setter
    def description(self, description, toolCall=None):
        from dashboard.tasks import send_object_to_clients
        d = AgentInstanceDescriptionLog(
            agent=self.agent,
            agent_instance=self,
            description=description,
            toolCall=toolCall
        )
        d.save()
        send_object_to_clients(self)

    def get_tool_function(self, full_function_name):
            
            # Ensure tools are set up
            # This is called here to guarantee tool_instances and toolname_to_definition are populated
            # before as_client_dict accesses history_limiting_rules or other tool-related data.
            self._setup_tools()
            # First, check if it's a built-in tool function (e.g., 'fs_read')
            # Built-in tools are stored in self.tool_instances by their full function name (e.g., 'filesystem_read')
            # and self.toolname_to_definition maps them to their ToolDefinition.
            print("get_tool_function", full_function_name, self)
            print(self.tool_instances)
            if full_function_name in self.tool_instances:
                tool_instance = self.tool_instances[full_function_name]
                tool_def = self.toolname_to_definition[full_function_name]

                # For built-in tools, the function name directly maps to a method on the instance
                # We need to get the arguments from the tool_instance's 'functions' dictionary
                # and the callable method using getattr.
                if hasattr(tool_instance, 'functions') and full_function_name in tool_instance.functions:
                    return {
                        "arguments": tool_instance.functions[full_function_name]["parameters"],
                        "callable": getattr(tool_instance, full_function_name),
                        "tool_definition_id": tool_def.pk
                    }
                else:
                    raise ValueError(f"Built-in tool function '{full_function_name}' found, but its definition or callable method is missing on the instance.")

            # If not a direct built-in function, check if it's an MCP tool function (e.g., 'apple-mcp.list_files')
            # MCP clients are stored in self.tool_instances keyed by their tool_def.name (e.g., 'apple-mcp').
            if '.' in full_function_name:
                mcp_client_name, mcp_tool_method_name = full_function_name.split('.', 1)
                if mcp_client_name in self.tool_instances:
                    mcp_client_instance = self.tool_instances[mcp_client_name]
                    tool_def = self.toolname_to_definition[mcp_client_name] # MCPClient instances are mapped by tool_def.name

                    if isinstance(mcp_client_instance, MCPClient):
                        # For MCPClient, the callable is always `invoke_tool`,
                        # and the actual tool method name is passed as an argument.
                        # The arguments for the specific MCP tool method need to be dynamically
                        # fetched via the MCPClient itself, which typically involves an async call.
                        # For now, we return a placeholder, acknowledging this needs future refinement.
                        # TODO: Implement a mechanism to dynamically fetch the input schema for mcp_tool_method_name
                        #       from the MCPClient instance when the tool function is requested.
                        return {
                            "arguments": {"type": "object", "properties": {}}, # Placeholder, actual schema needs to be fetched from MCPClient.list_tools()
                            "callable": lambda **kwargs: mcp_client_instance.invoke_tool(mcp_tool_method_name, kwargs),
                            "tool_definition_id": tool_def.pk
                        }

            raise ValueError(f"Tool function '{full_function_name}' not found or not enabled for this agent instance.")

    def save(self, send_to_client=True, *args, **kwargs):
        from dashboard.tasks import send_object_to_clients
        is_new = self.pk is None
        old_system_pk = None
        if not is_new:
            # Fetch the old system pk before the save to detect changes
            try:
                old_system_pk = AgentInstance.objects.values_list('system_id', flat=True).get(pk=self.pk)
            except AgentInstance.DoesNotExist:
                pass # This can happen if the object is being created in a weird state

        print(f"AgentInstance.save() called for pk={self.pk}, is_new={is_new}")
        super().save(*args, **kwargs)

        # Trigger tool lifecycle check if the system was newly assigned or changed
        current_system_pk = self.system.pk if self.system else None
        print(f"AgentInstance.save(): old_system_pk={old_system_pk}, current_system_pk={current_system_pk}")
        if self.system and (is_new or old_system_pk != current_system_pk):
            print(f"AgentInstance.save(): Triggering celery_trigger_tool_lifecycle_task for instance {self.instance_pk}")
            from agent.tasks import celery_trigger_tool_lifecycle_task
            # Add a small delay to ensure the save transaction is committed before the task runs
            celery_trigger_tool_lifecycle_task.apply_async(args=[self.instance_pk], countdown=1)
        else:
            print(f"AgentInstance.save(): Not triggering celery_trigger_tool_lifecycle_task for instance {self.instance_pk}. Condition: self.system={bool(self.system)}, is_new={is_new}, old_system_pk={old_system_pk}, current_system_pk={current_system_pk}")

        if send_to_client:
            send_object_to_clients(self)

    def as_client_dict(self):
        model = self.model or self.agent.model
        model_name = model.name if model else 'N/A'
        model_id = model.pk if model else None

        # Ensure tools are set up
        # This is called here to guarantee tool_instances and toolname_to_definition are populated
        # before as_client_dict accesses history_limiting_rules or other tool-related data.
        self._setup_tools()

        all_rule_templates = []
        for tool_instance_or_client in self.tool_instances.values():
            if hasattr(tool_instance_or_client, 'get_history_limiting_rules'):
                all_rule_templates.extend(tool_instance_or_client.get_history_limiting_rules())
            elif isinstance(tool_instance_or_client, MCPClient):
                # MCPClient does not expose history limiting rules directly in the same way.
                # If MCP tools eventually have their own limiting rules, this logic would need to be extended.
                pass # Currently, MCPClient does not provide history limiting rules this way

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
            'id': self.instance_pk,
            'agent_id': self.agent.agent_pk, 
            'created_at': self.created_at.isoformat(), 
            'name': self.name, 
            'description': self.description,
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
        newInstance = AgentInstance()
        newInstance.agent = self.agent
        newInstance.model = self.model
        newInstance.name = f'Cloned {self.name}'
        newInstance.status = self.status
        newInstance.workingdir = self.workingdir
        newInstance.save()
        if self.description:
            AgentInstanceDescriptionLog.objects.create(agent_instance=newInstance, description=self.description)
        paths = set()
        for ctxitem in self.filesystemTool.get_loaded_items():
            paths.add(ctxitem.path)
        for path in paths:
            if os.path.isdir(path):
                newInstance.filesystemTool.directories.load(path=path)
            else:
                newInstance.filesystemTool.load(path=path)
        for message in self.get_conversation_messages(30):
            if message['role'] in ['assistant', 'user'
                ] and 'content' in message:
                newInstance.add_to_conversation(role=message['role'],
                    content=message['content'])
        return newInstance

    def add_to_conversation(self, role, content):
        c = ConversationMessage()
        c.agent = self.agent
        c.agentInstance = self
        c.role = role
        c.data = {'parts': [{'content': content}]}
        c.save()
        return c

    def start_or_continue(self):
        from agent.tasks import celery_create_query
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
        print("_setup_tools", self)
        self.tool_instances = {} # Maps full_function_name to tool instance for built-in, or tool_def.name to MCPClient instance
        self.toolname_to_definition = {} # Maps full_function_name (or tool_def.name for MCPClient) to ToolDefinition object

        # Always load all built-in tools
        from tools_common.models  import ToolDefinition as TS_ToolDefinition # Alias to avoid conflict with agent.ToolDefinition if it existed
        for tool_name, tool_class in BUILTIN_TOOL_CLASS_MAP.items():
            try:
                instance = tool_class(self)
                # Try to find the ToolDefinition for this built-in tool
                tool_def, created = TS_ToolDefinition.objects.get_or_create(
                    name=tool_name,
                    defaults={'display_name': tool_name.replace('_', ' ').title(), 'is_builtin': True, 'description': f"Built-in {tool_name} tool."}
                )
                if created:
                    print(f"Created ToolDefinition for built-in tool: {tool_name}")

                for func_name, func_details in instance.functions.items():
                    # Map the full function name (e.g., 'filesystem_read') to the tool instance and its definition
                    self.tool_instances[func_name] = instance
                    self.toolname_to_definition[func_name] = tool_def
            except Exception as e:
                print(f"Error initializing built-in tool {tool_name} for AgentInstance {self.instance_pk}: {e}")

        print("foobr", self.tool_instances)
        # Load external MCP tools only if the agent has them selected AND they are installed and running on the system
        if self.agent and self.system:
            from tools_mcp.models import MCPServer # Import here to avoid circular dependency

            for tool_def in self.agent.available_tools.filter(is_builtin=False):
                try:
                    # Find the active installation for this tool_def on this system
                    installation = self.system.tool_installations.get(tool_definition=tool_def, status='running')

                    # An installation must exist and have an associated MCPServer record
                    if installation and hasattr(installation, 'mcp_server_connection'):
                        mcp_server_record = installation.mcp_server_connection
                        client = MCPClient(name=tool_def.name, mcp_server=mcp_server_record, agent_instance=self)

                        # Store the MCPClient instance keyed by the tool_def.name (e.g., 'apple-mcp')
                        self.tool_instances[tool_def.name] = client
                        self.toolname_to_definition[tool_def.name] = tool_def
                    else:
                        print(f"Warning: MCP tool '{tool_def.name}' installation or its MCPServer record not found or not running on system '{self.system.name}'. Skipping.")

                except installation._meta.model.DoesNotExist:
                    print(f"Warning: MCP tool '{tool_def.name}' not installed on system '{self.system.name}'. Skipping.")
                except Exception as e:
                    print(f"Error initializing MCP tool {tool_def.name} for AgentInstance {self.instance_pk}: {e}")
        elif self.agent and not self.system:
            # If agent has MCP tools but no system is assigned, log a warning
            if self.agent.available_tools.filter(is_builtin=False).exists():
                print(f"Warning: Agent {self.agent.name} has external MCP tools selected, but AgentInstance {self.instance_pk} has no system assigned. Skipping MCP tool loading.")

