from django.contrib import admin
from .models.tool_definition import ToolDefinition
from .models.tool_installation import ToolInstallation
from .models.tool_installation_log import ToolInstallationLog

@admin.register(ToolDefinition)
class ToolDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'is_builtin', 'repository_url', 'execution_mode')
    search_fields = ('name', 'display_name', 'description')
    list_filter = ('is_builtin', 'execution_mode', 'transport_type')

@admin.register(ToolInstallation)
class ToolInstallationAdmin(admin.ModelAdmin):
    list_display = ('tool_definition', 'system', 'agent_instance', 'status', 'local_path', 'created_at')
    list_filter = ('status', 'system', 'tool_definition__is_builtin', 'agent_instance')
    search_fields = ('tool_definition__name', 'tool_definition__display_name', 'system__name', 'local_path')
    raw_id_fields = ('tool_definition', 'system', 'agent_instance')

@admin.register(ToolInstallationLog)
class ToolInstallationLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'tool_installation', 'level', 'message')
    list_filter = ('level', 'tool_installation__system__name')
    search_fields = ('message', 'tool_installation__tool_definition__name')
    raw_id_fields = ('tool_installation',)
