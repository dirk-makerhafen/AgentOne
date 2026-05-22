"""Admin for the TaskDefinition model."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.tasks.task_definition import TaskDefinition


@admin.register(TaskDefinition)
class TaskDefinitionAdmin(admin.ModelAdmin):
    """Admin for task definitions."""

    list_display: tuple[str, ...] = (
        "id", "created_at", "name", "parent_project", "parent_agent", "parent_skill",
    )
    list_display_links: tuple[str, ...] = ("id",)
