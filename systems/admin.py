from django.contrib import admin
from .models import System

@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    list_display = ('pk', 'name', 'status', 'executor_mode', 'executor_url', 'last_heartbeat')
    list_display_links = ('pk', 'name')
    list_filter = ('status', 'executor_mode')
    search_fields = ('name', 'description', 'executor_url', 'raw_data')
    
    fieldsets = (
        ('Core Information', {
            'fields': ('name', 'description', 'status', 'last_heartbeat')
        }),
        ('Executor Configuration', {
            'fields': ('executor_mode', 'executor_url', 'executor_api_key')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Raw Data', {
            'fields': ('raw_data',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('last_heartbeat', 'created_at', 'updated_at', 'raw_data')
    list_per_page = 25
