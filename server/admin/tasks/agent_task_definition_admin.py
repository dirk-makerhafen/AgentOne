from django.contrib import admin
from server.models.tasks.task_definition import TaskDefinition

@admin.register(TaskDefinition)
class TaskDefinitionAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at",  'task_type', 'name', 'requires_approval', 'max_retries', 'retry_delay',  'trigger',"path","parent_skill", "parent_agent", "parent_project" )
    list_display_links = ("id",)
    list_filter = ('task_type', 'requires_approval', 'created_at', "trigger", "name")
    search_fields = ('name', 'description', 'task_type')

    fieldsets = (
        (None, {
            'fields': ('task_type', 'name', 'trigger', 'description', 'function_schema' )
        }),
        ('Execution Parameters', {
            'fields': ('requires_approval', 'max_retries', 'retry_delay',  )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
