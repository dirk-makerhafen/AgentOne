from django.contrib import admin
from server.models.system import System

@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'os', 'executor_mode', 'last_heartbeat', 'created_at')
    list_display_links = ('name',)
    list_filter = ('status', 'os', 'executor_mode', 'created_at')
    search_fields = ('name', 'description', 'executor_url', 'executor_api_key', 'raw_data')
    readonly_fields = ('created_at', 'updated_at', 'last_heartbeat')
    list_per_page = 25
    
    fieldsets = (
        ('General Information', {
            'fields': ('name', 'description', 'status', 'os')
        }),
        ('Executor Configuration', {
            'fields': ('executor_mode', 'executor_url', 'executor_api_key'),
            'description': 'Settings for how tools are executed on this system.'
        }),
        ('Runtime Info', {
            'fields': ('last_heartbeat', 'raw_data'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
