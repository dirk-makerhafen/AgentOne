from django.contrib import admin
from server.models.tasks.agent_task_run import AgentTaskRun, AgentTaskRunSubtask


class AgentTaskRunSubtaskInline(admin.TabularInline):
    model = AgentTaskRunSubtask
    # Since it's a self-referencing relationship with two FKs to the same model,
    # you must specify which one is the 'parent' for the inline.
    fk_name = 'parent'
    extra = 1


@admin.register(AgentTaskRun)
class AgentTaskRunAdmin(admin.ModelAdmin):
    # 'agent_instance_version__agent__name', 'agent_task_call', 'agent_task_definition__name', 
    list_display = ('id', "created_at",'status', "arguments_json", 'result_json')
    list_display_links = ('id',)
    list_filter = ('status', 'created_at')
    #search_fields = ( 'agent_task_call__id', 'agent_task_call__agent_task_instance__name')
    #autocomplete_fields = ('agent_task_call',)
    readonly_fields = ('created_at', 'updated_at')
    '''
    fieldsets = (
        (None, {
            'fields': ('agent_task_call', 'status', "agent_task_instance")
        }),
        ('Arguments', {
            'fields': ( "arguments_json", "taskrun_arg_references"),
        }),
        ('Results', {
            'fields': ('result_json', 'taskrun_result_references'),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    '''
    list_per_page = 25
    #inlines = [AgentTaskRunSubtaskInline]
