from django.contrib import admin
from .models import ToolCall, ToolResponse
from django.contrib import admin
from .models import ToolDefinition, ToolInstallation, ToolInstallationLog

@admin.register(ToolCall)
class ToolCallAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agentInstance', 'function_name', 'status', 'raw_data')
    list_display_links = ('pk', 'agentInstance')
    list_filter = ('status', 'function_name', 'agentInstance__name')
    search_fields = ('function_name', 'data', 'raw_data', 'agentInstance__name')
    autocomplete_fields = ('agentInstance', 'conversationMessage')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ToolResponse)
class ToolResponseAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'toolCall', 'status', 'raw_data')
    list_display_links = ('pk', 'toolCall')
    list_filter = ('status', 'toolCall__function_name')
    search_fields = ('data', 'raw_data', 'toolCall__function_name')
    autocomplete_fields = ('toolCall',)
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

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
