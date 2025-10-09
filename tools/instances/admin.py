from django.contrib import admin
from tools.instances.models.tool_instance import ToolInstance

@admin.register(ToolInstance)
class ToolInstanceAdmin(admin.ModelAdmin):
    list_display = ('tool_installation', 'status', 'process_id', 'endpoint_url', 'created_at')
    list_filter = ('status', 'tool_installation__system', 'tool_installation__tool_definition')
    search_fields = (
        'tool_installation__tool_definition__name',
        'tool_installation__tool_definition__display_name',
        'tool_installation__system__name',
        'endpoint_url',
        'last_error'
    )
    readonly_fields = ('status', 'process_id', 'endpoint_url', 'last_error', 'created_at', 'updated_at')
    raw_id_fields = ('tool_installation',)
    fieldsets = (
        (None, {
            'fields': ('tool_installation',)
        }),
        ('Runtime Details', {
            'fields': ('status', 'process_id', 'endpoint_url', 'last_error'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
