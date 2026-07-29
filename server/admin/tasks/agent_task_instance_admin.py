"""Admin for the TaskInstance model (formerly AgentTaskInstance)."""
from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from server.models.tasks.task_instance import TaskInstance


@admin.register(TaskInstance)
class AgentTaskInstanceAdmin(admin.ModelAdmin):
    """Admin for task instance records."""

    list_display: tuple[str, ...] = ("id", "created_at", "session", "created_at")
    list_display_links: tuple[str, ...] = ("id",)
    list_filter: tuple[str, ...] = ("session_version", "created_at")
    search_fields: tuple[str, ...] = ("session__name",)
    autocomplete_fields: tuple[str, ...] = ("session_version",)
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    raw_id_fields: tuple[str, ...] = (
        "taskinstance_arg_references",
        "taskinstance_result_references",
        "taskinstances_on_success_callbacks",
        "taskinstances_on_error_callbacks",
        "taskinstances_before_run_hooks",
        "taskinstances_after_run_hooks",
        "child_instances",
    )
    list_per_page: int = 25

    fieldsets: tuple[tuple[str, dict[str, Any]], ...] = (
        (None, {
            "fields": (
                "session_version",
            ),
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
        }),
    )
