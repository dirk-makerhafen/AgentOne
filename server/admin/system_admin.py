"""Admin for the System model."""
from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from server.models.system import System


@admin.register(System)
class SystemAdmin(admin.ModelAdmin):
    """Admin for system (executor) configurations."""

    list_display: tuple[str, ...] = (
        "name", "status", "os", "executor_mode", "last_heartbeat", "created_at",
    )
    list_display_links: tuple[str, ...] = ("name",)
    list_filter: tuple[str, ...] = ("status", "os", "executor_mode", "created_at")
    search_fields: tuple[str, ...] = (
        "name", "description", "executor_url", "executor_api_key", "raw_data",
    )
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at", "last_heartbeat")
    list_per_page: int = 25

    fieldsets: tuple[tuple[str, dict[str, Any]], ...] = (
        ("General Information", {
            "fields": ("name", "description", "status", "os"),
        }),
        ("Executor Configuration", {
            "fields": ("executor_mode", "executor_url", "executor_api_key"),
            "description": "Settings for how tools are executed on this system.",
        }),
        ("Runtime Info", {
            "fields": ("last_heartbeat", "raw_data"),
            "classes": ("collapse",),
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
