"""Admin for the SettingsModel (formerly AgentProfile)."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.settings import SettingsModel


@admin.register(SettingsModel)
class SettingsModelAdmin(admin.ModelAdmin):
    """Admin for agent/session settings profiles."""

    list_display: tuple[str, ...] = ("aimodel", "scheduler_strategy", "created_at")
    search_fields: tuple[str, ...] = ("aimodel__name", "scheduler_strategy")
    list_filter: tuple[str, ...] = ("aimodel", "scheduler_strategy", "created_at")
    autocomplete_fields: tuple[str, ...] = ("aimodel",)
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    list_per_page: int = 25
