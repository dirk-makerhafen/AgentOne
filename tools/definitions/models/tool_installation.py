from django.db import models
from core.models.base_model import BaseModel
from systems.models.system import System
from .tool_definition import ToolDefinition
from django.core.validators import MaxValueValidator, MinValueValidator

class ToolInstallation(BaseModel):
    class ToolInstallationStatusChoices(models.TextChoices):
        INSTALLING = 'installing', 'Installing'
        INSTALLED = 'installed', 'installed'
        UNINSTALLING = 'uninstalling', 'Uninstalling'
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
    status = models.CharField(max_length=20, choices=ToolInstallationStatusChoices.choices, default=ToolInstallationStatusChoices.INSTALLING)
    local_path = models.CharField(max_length=1024, blank=True, null=True, help_text="The installation path on the remote system.")
    max_parallel_instances = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(64)],
        help_text="Maximum number of parallel instances allowed for this tool installation."
    )

    class Meta:
        unique_together = ('tool_definition', 'system', 'agent_instance')
        ordering = ['-created_at']

    def __str__(self):
        instance_str = f" for Instance {self.agent_instance.pk}" if self.agent_instance else " (Shared)"
        return f"{self.tool_definition.display_name} on {self.system.name}{instance_str} [{self.status}]"

    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            self.send_object_to_clients()

    def as_client_dict(self):
        # Find the latest running or stopped instance for this installation to report to the client
        # This logic needs to be updated to consider max_parallel_instances for client display
        # For now, we still report the *latest* status, but the client might need to query for all running instances.
        latest_instance = self.instances.order_by('-created_at').first()

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
            'max_parallel_instances': self.max_parallel_instances, # Add the new field
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            # Include details from the latest associated instance
            'instance_status': latest_instance.status if latest_instance else 'not_run',
            'instance_id': latest_instance.pk if latest_instance else None,
        }
    def get_delete_broadcast_payload(self):
        return {
            'object': 'ToolInstallationDeleted',
            'installation_pk': self.pk,
            'system_pk': self.system.pk
        }
