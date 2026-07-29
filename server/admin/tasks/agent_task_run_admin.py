"""Admin for the AgentTaskRun model."""
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from server.models.tasks.agent_task_run import AgentTaskRun


@admin.register(AgentTaskRun)
class AgentTaskRunAdmin(admin.ModelAdmin):
    """Admin for agent task run records."""

    list_display: tuple[str, ...] = (
        "id", "created_at", "status",
        "agent_task_call_id", "task_instance",  "arguments_json", "result_json",
    )
    list_display_links: tuple[str, ...] = ("id",)
    list_filter: tuple[str, ...] = ("status", "created_at")
    readonly_fields: tuple[str, ...] = (
        "created_at", "updated_at", "arguments_json", "result_json", "taskrun_arg_references",    "taskrun_result_references",
        "agent_task_call", "task_instance",  "task_definition_version", "session_version"
    )
   
    list_per_page: int = 25

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).select_related(
            "task_instance", "agent_task_call",
        )
