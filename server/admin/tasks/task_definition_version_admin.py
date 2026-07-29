"""Admin for the TaskDefinitionVersion model."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.tasks.task_definition_version import TaskDefinitionVersion


@admin.register(TaskDefinitionVersion)
class TaskDefinitionVersionAdmin(admin.ModelAdmin):
    """Admin for task definition versions."""

    list_display: tuple[str, ...] = (
        "id", "created_at", "requires_approval", "max_retries",
        "retry_delay", "path", "commit",
    )
    list_display_links: tuple[str, ...] = ("id",)
    search_fields: tuple[str, ...] = ("task_definition__name", "commit")
