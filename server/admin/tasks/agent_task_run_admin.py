"""Admin for the AgentTaskRun model."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.tasks.agent_task_run import AgentTaskRun


@admin.register(AgentTaskRun)
class AgentTaskRunAdmin(admin.ModelAdmin):
    """Admin for agent task run records."""

    list_display: tuple[str, ...] = (
        "id", "created_at", "status",
        "task_definition_version__task_definition__name",
        "arguments_json", "result_json",
    )
    list_display_links: tuple[str, ...] = ("id",)
    list_filter: tuple[str, ...] = ("status", "created_at")
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    list_per_page: int = 25
