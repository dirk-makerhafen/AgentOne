
from django.contrib import admin
from server.models.tasks.task_definition_version import TaskDefinitionVersion

@admin.register(TaskDefinitionVersion)
class TaskDefinitionVersionAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at",   'requires_approval', 'max_retries', 'retry_delay',"path" , "commit")
    list_display_links = ("id",)
