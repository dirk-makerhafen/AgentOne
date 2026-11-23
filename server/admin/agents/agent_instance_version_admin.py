"""Admin for the SessionVersionModel (formerly AgentInstanceVersion)."""
from django.contrib import admin
from django.http import HttpRequest

from server.admin.filters import CreatedAtRangeFilter
from server.models.sessions.session_version import SessionVersionModel


@admin.register(SessionVersionModel)
class SessionVersionModelAdmin(admin.ModelAdmin):
    """Admin for session version instances."""

    list_display: tuple[str, ...] = ("id", "created_at", "workspace", "session")
    list_display_links: tuple[str, ...] = ("id", "session")
    search_fields: tuple[str, ...] = ("name", "session")
    # A RelatedFieldListFilter on session (71k rows) renders a multi-MB
    # dropdown and issues a query per choice via SessionVersionModel.__str__.
    list_filter: tuple[str, ...] = (CreatedAtRangeFilter,)
    list_select_related: tuple[str, ...] = ("workspace", "session")
    list_per_page: int = 25
    show_full_result_count: bool = False
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    raw_id_fields: tuple[str, ...] = ("child_session_versions",)
