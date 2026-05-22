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
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    list_per_page: int = 25

    fieldsets: tuple[tuple[str, dict[str, Any]], ...] = (
        (None, {
            "fields": (
                "taskinstances_on_success_callbacks",
                "taskinstances_on_error_callbacks",
                "session_version",
            ),
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
        }),
    )
