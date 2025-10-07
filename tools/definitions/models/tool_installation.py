from django.db import models
from core.models.base_model import BaseModel
from systems.models.system import System
from .tool_definition import ToolDefinition

class ToolInstallation(BaseModel):
    class Status(models.TextChoices):
        NOT_INSTALLED = 'not_installed', 'Not Installed'
        INSTALLING = 'installing', 'Installing'
        INSTALLED = 'installed', 'Installed'
        RUNNING = 'running', 'Running'
        STOPPED = 'stopped', 'Stopped'
        ERROR = 'error', 'Error'

    tool_definition = models.ForeignKey(ToolDefinition, on_delete=models.CASCADE, related_name='installations')
    system = models.ForeignKey("systems.System", on_delete=models.CASCADE, related_name='tool_installations')
    agent_instance = models.ForeignKey(
        'agents.AgentInstance',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='tool_installations',
        help_text="The specific agent instance this installation is dedicated to. Null for shared tools."
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_INSTALLED)
    local_path = models.CharField(max_length=1024, blank=True, null=True, help_text="The installation path on the remote system.")
    process_id = models.IntegerField(blank=True, null=True, help_text="The PID of the running tool process on the remote system.")
    assigned_port = models.IntegerField(blank=True, null=True, help_text="The network port assigned to the running service.")
    mcp_server = models.OneToOneField(
        'instances.ToolInstance', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='installation',
        help_text="The ToolInstance that this ToolInstallation manages the connection for."
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
            self.send_object_to_clients()

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
