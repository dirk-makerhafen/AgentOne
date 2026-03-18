
from django.contrib import admin
from server.models.tasks.agent_task_run import AgentTaskRun, AgentTaskRunSubtask

@admin.register(AgentTaskRunSubtask)
class AgentTaskRunSubtaskAdmin(admin.ModelAdmin):
    pass