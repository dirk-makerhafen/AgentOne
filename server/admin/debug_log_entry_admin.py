"""Admin for the DebugLogEntry model."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.debug_log_entry import DebugLogEntry


@admin.register(DebugLogEntry)
class DebugLogEntryAdmin(admin.ModelAdmin):
    """Admin for debug log entries."""

    list_display: tuple[str, ...] = ("id", "session", "event", "status", "created_at")
    list_filter: tuple[str, ...] = ("status", "event", "created_at")
    search_fields: tuple[str, ...] = ("event", "status", "session__name")
    autocomplete_fields: tuple[str, ...] = ("session",)
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    list_per_page: int = 25
