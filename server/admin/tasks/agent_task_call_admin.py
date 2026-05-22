"""Admin for the AgentTaskCall model."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.tasks.agent_task_call import AgentTaskCall


@admin.register(AgentTaskCall)
class AgentTaskCallAdmin(admin.ModelAdmin):
    """Admin for agent task call records."""

    list_display: tuple[str, ...] = (
        "id", "session", "session_version", "status", "status_detail",
        "created_at", "taskcall_result_run",
        "task_definition_version__task_definition__name",
        "carguments_json",
    )
    list_display_links: tuple[str, ...] = ("id",)
    list_filter: tuple[str, ...] = ("status", "created_at")
    search_fields: tuple[str, ...] = ("task_instance__name",)
    autocomplete_fields: tuple[str, ...] = ("session", "session_version")
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    filter_horizontal: tuple[str, ...] = (
        "taskcall_arg_references",
        "taskcall_on_success_callbacks",
        "taskcall_on_error_callbacks",
    )
    list_per_page: int = 25
