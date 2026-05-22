"""Admin for the QueryMessage model."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.queries.query_message import QueryMessage


@admin.register(QueryMessage)
class QueryMessageAdmin(admin.ModelAdmin):
    """Admin for individual query messages within a query."""

    search_fields: tuple[str, ...] = ("id",)
    list_display: tuple[str, ...] = ("id", "role", "tokens", "created_at")
    list_display_links: tuple[str, ...] = ("id",)
    list_filter: tuple[str, ...] = ("role", "created_at")
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    list_per_page: int = 25
