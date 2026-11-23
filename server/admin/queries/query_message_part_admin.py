"""Admin for the QueryMessagePart model."""
from django.contrib import admin

from server.admin.filters import CreatedAtRangeFilter
from server.models.queries.query_message_part import QueryMessagePart


@admin.register(QueryMessagePart)
class QueryMessagePartAdmin(admin.ModelAdmin):
    """Admin for individual parts of a query message."""

    list_display: tuple[str, ...] = (
        "id", "query_message", "content_type", "tokens", "created_at",
    )
    list_display_links: tuple[str, ...] = ("id",)
    list_filter: tuple[str, ...] = (CreatedAtRangeFilter, "content_type")
    search_fields: tuple[str, ...] = ("id",)
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    raw_id_fields: tuple[str, ...] = (
        "query_message", "source_message_part", "content", "template_data",
    )
    list_select_related: tuple[str, ...] = ("query_message",)
    ordering: tuple[str, ...] = ("-id",)
    list_per_page: int = 25
    # Avoid the expensive COUNT(*) over the whole table on every changelist.
    show_full_result_count: bool = False
