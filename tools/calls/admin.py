from django.contrib import admin
from .models.tool_call import ToolCall
from .models.tool_response import ToolResponse
from django.contrib import admin

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
