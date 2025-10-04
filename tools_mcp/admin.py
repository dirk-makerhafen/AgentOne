from django.contrib import admin
from .models import MCPServer

@admin.register(MCPServer)
class MCPServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'endpoint_url', 'status', 'enabled', 'created_at', 'updated_at')
    list_filter = ('status', 'enabled')
    search_fields = ('name', 'endpoint_url', 'last_error')
    readonly_fields = ('status', 'last_error', 'tools', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'endpoint_url', 'enabled')
        }),
        ('MCP Server Status', {
            'fields': ('status', 'last_error', 'tools'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
