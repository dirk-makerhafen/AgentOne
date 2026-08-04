"""Admin for the Response model."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.queries.response import Response


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    """Admin for query responses."""

    list_display: tuple[str, ...] = (
        "id", "query", "session_version__agent", "status",
        "prompt_tokens", "completion_tokens", "cached_tokens", "reasoning_tokens", "status", "created_at",
    )
    list_display_links: tuple[str, ...] = ("id",)
    list_filter: tuple[str, ...] = ("status",)
    autocomplete_fields: tuple[str, ...] = ()
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    list_per_page: int = 25
