"""Admin configuration for Cronjob model."""
from django.contrib import admin

from server.models.cron import Cronjob


@admin.register(Cronjob)
class CronjobAdmin(admin.ModelAdmin):
    """Admin for scheduled cron jobs."""

    list_display = (
        "id", "name", "schedule", "agent", "is_active", "is_archived",
        "parent_project", "last_run_at", "next_run_at", "total_runs",
    )
    list_filter = ("is_active", "is_archived", "parent_project")
    search_fields = ("name", "description", "agent__name")
    ordering = ("-created_at",)
