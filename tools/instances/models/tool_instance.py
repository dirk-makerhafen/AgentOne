from django.db import models
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models.base_model import BaseModel
from tools.instances.mcpclient import MCPClient

class ToolInstance(BaseModel):
    class ToolInstanceStatusChoices(models.TextChoices):
        STARTING = 'starting', 'Starting'
        RUNNING = 'running', 'Running'
        STOPPING = 'stopping', 'Stopping'
        STOPPED = 'stopped', 'Stopped'
        ERROR = 'error', 'Error'
    tool_installation = models.ForeignKey("definitions.ToolInstallation", on_delete=models.CASCADE, related_name='instances', help_text="The ToolInstallation this instance belongs to.")
    status = models.CharField(max_length=20, choices=ToolInstanceStatusChoices.choices, default=ToolInstanceStatusChoices.STARTING, help_text="Current runtime status of the tool instance.")
    process_id = models.IntegerField( blank=True, null=True, help_text="The PID of the running tool process on the remote system.")
    endpoint_url = models.URLField(max_length=2000, validators=[URLValidator(schemes=['http', 'https'])], help_text="The full URL of the tool's endpoint (if applicable).", blank=True, null=True)
    last_error = models.TextField(blank=True, null=True, help_text="Stores the last runtime error message.")

    @property
    def tools(self):
        return self.data.get("tools", [])
    @tools.setter
    def tools(self, new_tools):
        self.data["tools"] = new_tools
    
    @property
    def prompts(self):
        return self.data.get("prompts", [])
    @prompts.setter
    def prompts(self, new_prompts):
        self.data["prompts"] = new_prompts
    
    @property
    def templates(self):
        return self.data.get("templates", [])
    @templates.setter
    def templates(self, new_templates):
        self.data["templates"] = new_templates
    
    @property
    def resources(self):
        return self.data.get("resources", [])
    @resources.setter
    def resources(self, new_resources):
        self.data["resources"] = new_resources

    @property
    def mcp_client(self):
        if not hasattr(self, "_mcpclient"):
            self._mcp_client = MCPClient(system=self.tool_installation.system, process_id=self.pk )
        return self._mcp_client
    
    class Meta:
        ordering = ['-created_at']

    def as_client_dict(self):
        return {
            "object": "ToolInstance",
            "id": self.pk,
            "tool_installation_id": self.tool_installation.pk,
            "status": self.status,
            'status_display': self.get_status_display(),
            "process_id": self.process_id,
            "endpoint_url": self.endpoint_url,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "raw_data": self.data, # Expose the data field from BaseModel
        }

    def __str__(self):
        return f"Instance of {self.tool_installation.tool_definition.display_name} on {self.tool_installation.system.name} - Run at {self.created_at.strftime('%Y-%m-%d %H:%M')} [{self.status}]"
    
    def get_delete_broadcast_payload(self):
        return {
            'object': 'ToolInstanceDeleted',
            'tool_instance_pk': self.pk,
            'tool_installation_pk': self.tool_installation.pk
        }
