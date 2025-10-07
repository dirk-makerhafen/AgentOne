from django.contrib import admin
from django.contrib import admin

from .models.tool_definition import ToolDefinition
from .models.tool_installation import ToolInstallation
from .models.tool_installation_log import ToolInstallationLog

@admin.register(ToolDefinition)
class ToolDefinitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'is_builtin', 'repository_url')
    search_fields = ('name', 'display_name', 'description')
    list_filter = ('is_builtin',)

@admin.register(ToolInstallation)
class ToolInstallationAdmin(admin.ModelAdmin):
    list_display = ('tool_definition', 'system', 'status', 'local_path', 'process_id', 'assigned_port')
    list_filter = ('status', 'system', 'tool_definition__is_builtin')
    search_fields = ('tool_definition__name', 'tool_definition__display_name', 'system__name', 'local_path')
    raw_id_fields = ('tool_definition', 'system', 'mcp_server') # Use raw_id_fields for FKs to improve admin performance

@admin.register(ToolInstallationLog)
class ToolInstallationLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'tool_installation', 'level', 'message')
    list_filter = ('level', 'tool_installation__system__name')
    search_fields = ('message', 'tool_installation__tool_definition__name')
    raw_id_fields = ('tool_installation',)
