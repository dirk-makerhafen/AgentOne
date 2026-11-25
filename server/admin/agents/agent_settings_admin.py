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

    def has_delete_permission(self, request: HttpRequest, obj: SettingsModel | None = None) -> bool:
        """Never let the admin delete a referenced settings snapshot.

        ``AgentVersionModel.agent_settings`` and
        ``SessionVersionModel.session_settings`` use ``SET_NULL``: deleting a
        row here silently breaks every pinned version that points at it (their
        prompts then resolve through ``extends``). Use ``reload_all`` to repair
        any such versions.
        """
        return False
