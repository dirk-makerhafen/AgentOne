from django.db import models

from core.models.base_model import BaseModel

class ToolDefinition(BaseModel):
    class ToolDefinitionStatusChoices(models.TextChoices):
        NEW = 'new', 'New'
        UPDATING = 'updating', 'Updating'
        UP_TO_DATE = 'up_to_date', 'Up to Date'
        ERROR = 'error', 'Error'
        UNKNOWN = 'unknown', 'Unknown'

    class ExecutionMode(models.TextChoices):
        SHARED = 'shared', 'Shared Process'
        DEDICATED = 'dedicated', 'Dedicated Process per Instance'

    class TransportChoices(models.TextChoices):
        TCP = 'tcp', 'TCP Socket (HTTP/S)'
        STDIN_STDOUT = 'stdin_stdout', 'Standard I/O (stdin/stdout)'

    name = models.CharField(max_length=255, unique=True, help_text="Unique identifier for the tool, e.g., 'apple-mcp'.")
    display_name = models.CharField(max_length=255, help_text="User-friendly name, e.g., 'Apple MCP'.")
    description = models.TextField(blank=True, help_text="A brief description of what the tool does.")
    is_builtin = models.BooleanField(default=False, help_text="True if this is an internal tool (Python, Shell), False for external MCP tools.")
    is_active = models.BooleanField(default=True, help_text="Globally enable or disable this tool for all agents.")
    
    transport_type = models.CharField(max_length=20, choices=TransportChoices, default=TransportChoices.STDIN_STDOUT, help_text="The communication transport type for this tool.")
    execution_mode = models.CharField(max_length=20, choices=ExecutionMode.choices, default=ExecutionMode.SHARED, help_text="Determines if one process is shared across a system or if each agent instance gets a dedicated process.")

    repository_url = models.URLField(blank=True, null=True, help_text="The repository URL or PATH for external tools., path begins with file://")
    status = models.CharField(max_length=20, choices=ToolDefinitionStatusChoices.choices, default=ToolDefinitionStatusChoices.NEW)
    manifest_version = models.CharField(max_length=50, blank=True, null=True, help_text="The version from the tool's manifest file.")
    last_checked_at = models.DateTimeField(null=True, blank=True, help_text="When the manifest was last checked for updates.")

    available_on_all_systems = models.BooleanField(default=True, help_text="If true, this tool is available on all compatible systems by default.")
    available_on_systems = models.ManyToManyField('systems.System', blank=True, related_name='tool_definitions', help_text="A specific list of systems where this tool is available.")
 
    @property
    def manifest(self):
        return self.data.get("manifest", {})
    @manifest.setter
    def manifest(self, manifest):
        self.data["manifest"] = manifest
    
    def has_tool_name(self, name):
        if self.is_builtin:
            from tools.base.buildin_tools_map import BUILTIN_TOOL_CLASS_MAP
            return True if  BUILTIN_TOOL_CLASS_MAP[self.name].TOOLS.get(name, None) else False
        else:
            return len([x for x in self.manifest.get("tools",[]) if x["name"] == name]) > 0

    def to_llm_schema(self):
        """Converts the tool definition into the JSON schema format for LLM tool calling."""
        if self.is_builtin:
            from tools.base.buildin_tools_map import BUILTIN_TOOL_CLASS_MAP
            tool_class = BUILTIN_TOOL_CLASS_MAP.get(self.name)
            if not tool_class:
                return []
            
            schemas = []
            for func_name, func_details in tool_class.TOOLS.items():
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": func_name,
                        "description": func_details.get("description", ""),
                        "parameters": func_details.get("parameters", {"type": "object", "properties": {}})
                    }
                })
            return schemas
        else:
            # For external tools, we derive the schema from the manifest
            schemas = []
            for tool_info in self.manifest.get("tools", []):
                 schemas.append({
                    "type": "function",
                    "function": {
                        "name": tool_info.get("name"),
                        "description": tool_info.get("description", ""),
                        "parameters": tool_info.get("parameters", {"type": "object", "properties": {}})
                    }
                })
            return schemas
       
    def save(self, send_to_client=True, *args, **kwargs):
        from tools.definitions.tasks.refresh_definition_manifest import refresh_definition_manifest
        is_new = self.pk is None
        old_url = None
        if not is_new:
            old_instance = ToolDefinition.objects.get(pk=self.pk)
            old_url = old_instance.repository_url

        url_changed = (is_new and self.repository_url) or (not is_new and self.repository_url != old_url)
        if self.is_builtin:
            self.status = ToolDefinition.ToolDefinitionStatusChoices.UP_TO_DATE
        elif self.repository_url and url_changed:
            self.status = ToolDefinition.ToolDefinitionStatusChoices.UPDATING

        super().save(send_to_client=send_to_client, *args, **kwargs)

        if self.repository_url and url_changed and not self.is_builtin:
            refresh_definition_manifest.delay(self.pk)

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
            'status_display': self.get_status_display(),
            'manifest_version': self.manifest_version,
            'available_on_all_systems': self.available_on_all_systems,
            'available_on_systems': list(self.available_on_systems.values_list('pk', flat=True)),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
    
    def get_delete_broadcast_payload(self):
        return {
            'object': 'ToolDefinitionDeleted',
            'tool_def_pk': self.pk
        }

    def __str__(self):
        return f"{self.display_name} ({self.name})"
