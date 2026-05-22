"""Admin for the QueryMessagePart model."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.queries.query_message_part import QueryMessagePart


@admin.register(QueryMessagePart)
class QueryMessagePartAdmin(admin.ModelAdmin):
    """Admin for individual parts of a query message."""

    list_display: tuple[str, ...] = (
        "id", "query_message", "content_type", "tokens", "created_at",
    )
    list_display_links: tuple[str, ...] = ("id",)
    list_filter: tuple[str, ...] = ("content_type", "created_at")
    search_fields: tuple[str, ...] = ("id",)
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    list_per_page: int = 25
