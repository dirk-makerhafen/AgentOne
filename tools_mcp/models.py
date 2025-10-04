from django.db import models
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from typing import List, Dict, Any
from dashboard.tasks import send_object_to_clients
from tools_common.models  import ToolInstallation

class MCPServer(models.Model):
    STATUS_CHOICES = [
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error'),
        ('connecting', 'Connecting...'),
    ]

    TRANSPORT_CHOICES = [
        ('tcp', 'TCP Socket (HTTP/S)'),
        ('stdin_stdout', 'Standard I/O (stdin/stdout)'),
    ]

    name = models.CharField(max_length=255, unique=True, help_text="A user-friendly name for the MCP server.")

    endpoint_url = models.URLField(
        max_length=2000,
        validators=[URLValidator(schemes=['http', 'https'])],
        help_text="The full URL of the MCP endpoint (must be HTTP or HTTPS). Required for TCP transport.",
        blank=True,
        null=True
    )

    transport_type = models.CharField(
        max_length=20,
        choices=TRANSPORT_CHOICES,
        default='tcp',
        help_text="The communication transport type for the MCP server."
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='disconnected',
        help_text="Current connection status of the MCP server."
    )
    last_error = models.TextField(
        blank=True,
        null=True,
        help_text="Stores the last connection or tool-listing error message."
    )
    tools = models.JSONField(
        default=list,
        blank=True,
        help_text="JSON list of available tools discovered from the endpoint."
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether this MCP server's tools are enabled for agents."
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    tool_installation = models.OneToOneField(
        ToolInstallation, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='mcp_server_connection',
        help_text="The ToolInstallation that manages this MCP server instance."
    )

    def clean(self):
        """
        Custom validation to ensure data consistency based on transport_type.
        """
        super().clean()
        if self.transport_type == 'tcp':
            if not self.endpoint_url:
                raise ValidationError({'endpoint_url': 'Endpoint URL is required for TCP transport.'})
        elif self.transport_type == 'stdin_stdout':
            if self.endpoint_url:
                raise ValidationError({'endpoint_url': 'Endpoint URL must be null for stdin/stdout transport.'})

    def save(self, send_to_client=True, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        if send_to_client:
            from dashboard.tasks import send_object_to_clients
            send_object_to_clients(self)

    def as_client_dict(self):
        return {
            "object": "MCPServer",
            "id": self.pk,
            "name": self.name,
            "endpoint_url": self.endpoint_url,
            "transport_type": self.transport_type,
            "status": self.status,
            "last_error": self.last_error,
            "tools": self.tools,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __str__(self):
        if self.transport_type == 'tcp':
            return f"{self.name} (TCP: {self.endpoint_url})"
        else:
            return f"{self.name} (STDIO)"

    class Meta:
        verbose_name = "MCP Server"
        verbose_name_plural = "MCP Servers"
