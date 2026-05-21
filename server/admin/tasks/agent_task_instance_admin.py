from django.contrib import admin
from server.models.tasks.task_instance import TaskInstance

@admin.register(TaskInstance)
class AgentTaskInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", 'session', 'created_at')
    list_display_links = ("id", )
    list_filter = ('session_version',  'created_at')
    search_fields = ( 'session__name', )
    
    fieldsets = (
        (None, {
            'fields': ( "taskinstances_on_success_callbacks", "taskinstances_on_error_callbacks", 'session_version')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
