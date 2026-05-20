from django.contrib import admin
from server.models.tasks.task_definition import TaskDefinition

@admin.register(TaskDefinition)
class TaskDefinitionAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", 'name', 'parent_project', 'parent_agent', 'parent_skill')
    list_display_links = ("id",)
   