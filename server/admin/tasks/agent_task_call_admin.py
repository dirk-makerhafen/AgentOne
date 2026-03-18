from django.contrib import admin
from server.models.tasks.agent_task_call import AgentTaskCall

@admin.register(AgentTaskCall)
class AgentTaskCallAdmin(admin.ModelAdmin):
    list_display = ('id', 'agent_instance', 'agent_instance__agent__name','agent_instance_version', 'status', 'status_detail', 'created_at', "taskcall_result_run", 'agent_task_definition__name', "carguments_json")
    list_display_links = ('id',)
    list_filter = ('status', 'created_at')
    search_fields = ( 'agent_task_instance__name',)
    autocomplete_fields = ('agent_instance', 'agent_instance_version',)
    readonly_fields = ('created_at', 'updated_at')
    # Standard M2M fields without 'through' can still use filter_horizontal
    filter_horizontal = ('taskcall_arg_references', 'taskcall_on_success_callbacks', 'taskcall_on_error_callbacks')
   
    list_per_page = 25
