"""Admin for the HistoryLimitingRule model."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.history_limit import HistoryLimitingRule


@admin.register(HistoryLimitingRule)
class HistoryLimitAdmin(admin.ModelAdmin):
    """Admin for history-limiting rules."""

    list_display: tuple[str, ...] = ("rule_name", "agent", "group_name")
    list_filter: tuple[str, ...] = ("group_name", "agent", "created_at")
    search_fields: tuple[str, ...] = ("rule_name", "group_name", "description")
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    list_per_page: int = 25
