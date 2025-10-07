from django.db import models
from django.utils import timezone

from core.models.base_model import BaseModel

class ToolDefinition(BaseModel):
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
    
    TRANSPORT_CHOICES = [('tcp', 'TCP Socket (HTTP/S)'), ('stdin_stdout', 'Standard I/O (stdin/stdout)')]
    transport_type = models.CharField(max_length=20, choices=TRANSPORT_CHOICES, default='tcp', help_text="The communication transport type for this tool.")
    execution_mode = models.CharField(max_length=20, choices=ExecutionMode.choices, default=ExecutionMode.SHARED, help_text="Determines if one process is shared across a system or if each agent instance gets a dedicated process.")

    repository_url = models.URLField(blank=True, null=True, help_text="The Git repository URL for external tools.")
    manifest = models.JSONField(blank=True, null=True, help_text="The parsed manifest.json file from the repository.")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    manifest_version = models.CharField(max_length=50, blank=True, null=True, help_text="The version from the tool's manifest file.")
    last_checked_at = models.DateTimeField(null=True, blank=True, help_text="When the manifest was last checked for updates.")

    available_on_all_systems = models.BooleanField(default=True, help_text="If true, this tool is available on all compatible systems by default.")
    available_on_systems = models.ManyToManyField('systems.System', blank=True, related_name='tool_definitions', help_text="A specific list of systems where this tool is available.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.display_name} ({self.name})"

    def save(self, send_to_client=True, *args, **kwargs):
        from tools.definitions.tasks.refresh_tool_definition import fetch_and_update_tool_definition_manifest
        is_new = self.pk is None
        old_url = None
        if not is_new:
            old_instance = ToolDefinition.objects.get(pk=self.pk)
            old_url = old_instance.repository_url

        url_changed = (is_new and self.repository_url) or (not is_new and self.repository_url != old_url)
        if self.is_builtin:
            self.status = self.Status.UP_TO_DATE
        elif self.repository_url and url_changed:
            self.status = self.Status.UPDATING

        super().save(*args, **kwargs)

        if self.repository_url and url_changed and not self.is_builtin:
            fetch_and_update_tool_definition_manifest.delay(self.pk)

        if send_to_client:
            self.send_object_to_clients()

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
