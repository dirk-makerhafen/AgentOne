from django.contrib import admin
from server.models.tasks.agent_task_instance import AgentTaskInstance, AgentTaskInstanceSubtask
class TaskInstancetoTaskInstanceRelationInline(admin.TabularInline):
    model = AgentTaskInstanceSubtask
    # Since it's a self-referencing relationship with two FKs to the same model,
    # you must specify which one is the 'parent' for the inline.
    fk_name = 'parent'
    extra = 1
    
@admin.register(AgentTaskInstance)
class AgentTaskInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", 'agent_instance', 'created_at')
    list_display_links = ("id", )
    list_filter = ('agent_instance_version',  'created_at')
    search_fields = ( 'agent_instance__name', )
    #autocomplete_fields = ('agent_instance_version', 'agent_task_definition')
    
    fieldsets = (
        (None, {
            'fields': ( "taskinstances_on_success_callbacks", "taskinstances_on_error_callbacks", 'agent_instance_version')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
    inlines = [TaskInstancetoTaskInstanceRelationInline]
