from django.db import models
import traceback
from django.db import models
from systems.models import System
from .tasks import fetch_and_update_tool_definition_manifest
from common.models import ModelWithJsonData


class BaseTool():
    def __init__(self, agentInstance):
        self.agentInstance = agentInstance
   
    def get_functions(self):
        return {f"{f}":{
            "callable": self.__getattribute__(f), 
            "description": item["description"], 
            "arguments": item["parameters"]
        } for f, item in self.functions.items()}
    def get_content_parts(self):
        return []
    
class ToolCall(ModelWithJsonData):
    agent = models.ForeignKey("agent.Agent", on_delete=models.CASCADE, related_name='toolCalls')
    agentInstance = models.ForeignKey("agent.AgentInstance", on_delete=models.CASCADE, related_name='toolCalls')
    conversationMessage = models.ForeignKey("agent.ConversationMessage", null=True, default=None, on_delete=models.CASCADE, related_name='toolCalls')
    
    function_name = models.CharField(max_length=64)
    status = models.CharField(max_length=10, default='pending')

    @property
    def arguments(self):
        return self.data.get('arguments', {})

    @arguments.setter
    def arguments(self, data):
        self.data['arguments'] = data

    def save(self, send_to_client=True, *args, **kwargs):
        from dashboard.tasks import send_object_to_clients
        super().save(*args, **kwargs)
        if send_to_client:
            send_object_to_clients(self)

    def as_client_dict(self):
        toolResponse = self.toolResponses.last()
        return {
            'object': 'ToolCall', 
            'id': self.id, 
            "agent_id": self.agent_id,
            "agentInstance_id": self.agentInstance_id, 
            'created_at': self.created_at.isoformat(), 
            'function_name': self.function_name, 
            'arguments': self.arguments, 
            'status': self.status, 
            'result': toolResponse.data if toolResponse else None
        }

    def run(self):
        if self.status != 'pending':
            raise Exception('Tool call not pending, cant run')
        success = False
        result = None
        try:
            _function = self.agentInstance.get_tool_function(self.function_name)
            if _function is None:
                result = {'status': 'failed', 'message': f"No such function '{self.function_name}'"}
            else:
                err = None
                for arg in self.arguments:
                    if arg not in _function['arguments']:
                        err = f"Unknown argument '{arg}'"
                        break
                for arg in _function['arguments']:
                    if _function['arguments'][arg]['required'] == True and arg not in self.arguments:
                        err = f'Missing required argument {arg}'
                        break
                if err is not None:
                    result = {'status': 'failed', 'message': err}
                else:
                    success, result = _function['callable'](toolCall=self, **self.arguments)
        except Exception as e:
            result = {'status': 'failed', 'exception': f'{e} - {traceback.format_exc()}'}
        toolresponse = ToolResponse()
        toolresponse.agent = self.agentInstance.agent
        toolresponse.agentInstance = self.agentInstance
        toolresponse.toolCall = self
        toolresponse.status = 'success' if success else 'failed'
        toolresponse.data = result
        toolresponse.save()
        self.status = 'success' if success else 'failed'
        self.save(send_to_client=True)

class ToolResponse(ModelWithJsonData):
    agent = models.ForeignKey("agent.Agent", on_delete=models.CASCADE, related_name='toolResponses')
    agentInstance = models.ForeignKey("agent.AgentInstance", on_delete=models.CASCADE, related_name='toolResponses')
    toolCall = models.ForeignKey("ToolCall", null=True, default=None, on_delete=models.CASCADE, related_name='toolResponses')
    status = models.CharField(max_length=32, null=False, default='unknown')

    def save(self, send_to_client=True, *args, **kwargs):
        from dashboard.tasks import send_object_to_clients
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # The ToolCall object's update includes the result, so sending the response separately is redundant.
        # if send_to_client:
        #     send_object_to_clients(self)

class ToolDefinition(models.Model):
    """
    A central registry entry for a tool, whether built-in or external.
    This acts as a canonical definition for a tool's capabilities and source.
    """
    class Status(models.TextChoices):
        NEW = 'new', 'New'
        UPDATING = 'updating', 'Updating'
        UP_TO_DATE = 'up_to_date', 'Up to Date'
        ERROR = 'error', 'Error'
        UNKNOWN = 'unknown', 'Unknown'

    class ExecutionMode(models.TextChoices):
        SHARED = 'shared', 'Shared Process'
        DEDICATED = 'dedicated', 'Dedicated Process per Instance'

    name = models.CharField(max_length=255, unique=True, help_text="Unique identifier for the tool, e.g., 'apple-mcp'.")
    display_name = models.CharField(max_length=255, help_text="User-friendly name, e.g., 'Apple MCP'.")
    description = models.TextField(blank=True, help_text="A brief description of what the tool does.")

    is_builtin = models.BooleanField(default=False, help_text="True if this is an internal tool (Python, Shell), False for external MCP tools.")
    is_active = models.BooleanField(default=True, help_text="Globally enable or disable this tool for all agents.")

    TRANSPORT_CHOICES = [
        ('tcp', 'TCP Socket (HTTP/S)'),
        ('stdin_stdout', 'Standard I/O (stdin/stdout)'),
    ]
    transport_type = models.CharField(
        max_length=20,
        choices=TRANSPORT_CHOICES,
        default='tcp', # Default to TCP for new definitions
        help_text="The communication transport type for this tool."
    )

    execution_mode = models.CharField(
        max_length=20,
        choices=ExecutionMode.choices,
        default=ExecutionMode.SHARED,
        help_text="Determines if one process is shared across a system or if each agent instance gets a dedicated process."
    )

    # Fields for external tools
    repository_url = models.URLField(blank=True, null=True, help_text="The Git repository URL for external tools.")
    manifest = models.JSONField(blank=True, null=True, help_text="The parsed manifest.json file from the repository.")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    manifest_version = models.CharField(max_length=50, blank=True, null=True, help_text="The version from the tool's manifest file.")
    last_checked_at = models.DateTimeField(null=True, blank=True, help_text="When the manifest was last checked for updates.")

    # New fields for system assignment
    available_on_all_systems = models.BooleanField(default=True, help_text="If true, this tool is available on all compatible systems by default.")
    available_on_systems = models.ManyToManyField('systems.System', blank=True, related_name='tool_definitions', help_text="A specific list of systems where this tool is available.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.display_name} ({self.name})"

    def save(self, send_to_client=True, *args, **kwargs):
        is_new = self.pk is None
        old_url = None
        if not is_new:
            # Fetch the old instance from DB to compare the URL
            old_instance = ToolDefinition.objects.get(pk=self.pk)
            old_url = old_instance.repository_url

        url_changed = (is_new and self.repository_url) or (not is_new and self.repository_url != old_url)

        if self.is_builtin:
            self.status = self.Status.UP_TO_DATE
        elif self.repository_url and url_changed:
            self.status = self.Status.UPDATING

        super().save(*args, **kwargs)  # Save first to ensure a PK is available

        if self.repository_url and url_changed and not self.is_builtin:
            fetch_and_update_tool_definition_manifest.delay(self.pk)

        if send_to_client:
            from dashboard.tasks import send_object_to_clients
            send_object_to_clients(self)

    def as_client_dict(self):
        return {
            'object': 'ToolDefinition',
            'id': self.pk,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'is_builtin': self.is_builtin,
            'is_active': self.is_active,
            'transport_type': self.transport_type,
            'execution_mode': self.execution_mode,
            'repository_url': self.repository_url,
            'manifest': self.manifest,
            'status': self.status,
            'manifest_version': self.manifest_version,
            'available_on_all_systems': self.available_on_all_systems,
            'available_on_systems': list(self.available_on_systems.values_list('pk', flat=True)),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

class ToolInstallation(models.Model):
    """
    Represents the installation of a specific ToolDefinition on a specific System.
    This tracks the lifecycle and runtime state of a tool process.
    """
    class Status(models.TextChoices):
        NOT_INSTALLED = 'not_installed', 'Not Installed'
        INSTALLING = 'installing', 'Installing'
        INSTALLED = 'installed', 'Installed' # For tools that have an install step but are not running
        RUNNING = 'running', 'Running'
        STOPPED = 'stopped', 'Stopped'
        ERROR = 'error', 'Error'

    tool_definition = models.ForeignKey(ToolDefinition, on_delete=models.CASCADE, related_name='installations')
    system = models.ForeignKey(System, on_delete=models.CASCADE, related_name='tool_installations')
    agent_instance = models.ForeignKey(
        'agent.AgentInstance',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tool_installations',
        help_text="The specific agent instance this installation is dedicated to. Null for shared tools."
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_INSTALLED)

    # Runtime details managed by the remote Executor
    local_path = models.CharField(max_length=1024, blank=True, null=True, help_text="The installation path on the remote system.")
    process_id = models.IntegerField(blank=True, null=True, help_text="The PID of the running tool process on the remote system.")
    assigned_port = models.IntegerField(blank=True, null=True, help_text="The network port assigned to the running service.")

    # Link to the connection record used by the agent core
    mcp_server = models.OneToOneField(
        'tools_mcp.MCPServer', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='installation',
        help_text="The MCPServer that this ToolInstallation manages the connection for."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tool_definition', 'system', 'agent_instance')

    def __str__(self):
        if self.agent_instance:
            return f"{self.tool_definition.display_name} on {self.system.name} for Instance {self.agent_instance.pk} [{self.status}]"
        return f"{self.tool_definition.display_name} on {self.system.name} (Shared) [{self.status}]"


    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            from dashboard.tasks import send_object_to_clients
            send_object_to_clients(self)

    def as_client_dict(self):
        return {
            'object': 'ToolInstallation',
            'id': self.pk,
            'tool_definition_id': self.tool_definition.pk,
            'tool_definition_name': self.tool_definition.display_name,
            'system_id': self.system.pk,
            'system_name': self.system.name,
            'agent_instance_id': self.agent_instance.pk if self.agent_instance else None,
            'status': self.status,
            'local_path': self.local_path,
            'process_id': self.process_id,
            'assigned_port': self.assigned_port,
            'mcp_server_id': self.mcp_server.pk if self.mcp_server else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

class ToolInstallationLog(models.Model):
    """
    Stores a log entry related to a ToolInstallation process (install, start, stop).
    """
    class LogLevel(models.TextChoices):
        INFO = 'info', 'Info'
        ERROR = 'error', 'Error'

    tool_installation = models.ForeignKey(ToolInstallation, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10, choices=LogLevel.choices, default=LogLevel.INFO)
    message = models.TextField()

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"[{self.timestamp}] [{self.level.upper()}] {self.message}"


    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            from dashboard.tasks import send_object_to_clients
            send_object_to_clients(self)

    def as_client_dict(self):
        return {
            'object': 'ToolInstallationLog',
            'id': self.pk,
            'tool_installation_id': self.tool_installation.pk,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'message': self.message
        }
