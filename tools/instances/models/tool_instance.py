from django.db import models
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models.base_model import BaseModel

class ToolInstance(BaseModel):
    class Status(models.TextChoices):
        STARTING = 'starting', 'Starting'
        RUNNING = 'running', 'Running'
        STOPPING = 'stopping', 'Stopping'
        STOPPED = 'stopped', 'Stopped'
        ERROR = 'error', 'Error'

    tool_installation = models.ForeignKey(
        "definitions.ToolInstallation",
        on_delete=models.CASCADE,
        related_name='instances',
        help_text="The ToolInstallation this instance belongs to."
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.STARTING,
        help_text="Current runtime status of the tool instance."
    )
    process_id = models.IntegerField(
        blank=True,
        null=True,
        help_text="The PID of the running tool process on the remote system."
    )
    endpoint_url = models.URLField(
        max_length=2000,
        validators=[URLValidator(schemes=['http', 'https'])],
        help_text="The full URL of the tool's endpoint (if applicable).",
        blank=True,
        null=True
    )
    last_error = models.TextField(
        blank=True,
        null=True,
        help_text="Stores the last runtime error message."
    )

    class Meta:
        ordering = ['-created_at']

    def save(self, send_to_client=True, *args, **kwargs):
        super().save(*args, **kwargs)
        if send_to_client:
            # When an instance changes, we notify the client by sending the parent installation,
            # which now includes the latest instance status in its as_client_dict.
            self.tool_installation.send_object_to_clients()

    def as_client_dict(self):
        return {
            "object": "ToolInstance",
            "id": self.pk,
            "tool_installation_id": self.tool_installation.pk,
            "status": self.status,
            "process_id": self.process_id,
            "endpoint_url": self.endpoint_url,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __str__(self):
        return f"Instance of {self.tool_installation.tool_definition.display_name} on {self.tool_installation.system.name} - Run at {self.created_at.strftime('%Y-%m-%d %H:%M')} [{self.status}]"
    def delete(self, *args, **kwargs):
        from django.contrib.auth.models import User
        from core.tasks.send_websocket_update import celery_send_websocket_update

        tool_instance_pk_to_broadcast = self.pk
        tool_installation_pk_to_broadcast = self.tool_installation.pk

        super().delete(*args, **kwargs)

        # After deletion, broadcast the update to all users
        message_data = {
            'object': 'ToolInstanceDeleted',
            'tool_instance_pk': tool_instance_pk_to_broadcast,
            'tool_installation_pk': tool_installation_pk_to_broadcast # Include for UI updates
        }
        all_user_pks = User.objects.values_list('pk', flat=True)
        for pk in all_user_pks:
            celery_send_websocket_update.delay(message_data, user_pk=pk)
