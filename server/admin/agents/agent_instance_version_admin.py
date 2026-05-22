"""Admin for the SessionVersionModel (formerly AgentInstanceVersion)."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.sessions.session_version import SessionVersionModel


@admin.register(SessionVersionModel)
class SessionVersionModelAdmin(admin.ModelAdmin):
    """Admin for session version instances."""

    list_display: tuple[str, ...] = ("id", "created_at", "workspace", "session")
    list_display_links: tuple[str, ...] = ("id", "session")
    search_fields: tuple[str, ...] = ("name", "session")
    list_filter: tuple[str, ...] = ("session", "created_at")
    list_per_page: int = 25
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    filter_horizontal: tuple[str, ...] = ("child_session_versions",)
