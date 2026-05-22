"""Admin for the SessionModel (formerly AgentInstance)."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.sessions.session import SessionModel


@admin.register(SessionModel)
class SessionModelAdmin(admin.ModelAdmin):
    """Admin for session instances."""

    list_display: tuple[str, ...] = (
        "pk", "created_at", "name", "latest_session_version", "parent_session",
    )
    list_display_links: tuple[str, ...] = ("pk", "name", "latest_session_version")
    search_fields: tuple[str, ...] = ("name", "latest_session_version")
    list_filter: tuple[str, ...] = ("created_at",)
    list_per_page: int = 25
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
