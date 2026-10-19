"""Admin for the QueryMessagePart model."""
from datetime import timedelta

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone

from server.models.queries.query_message_part import QueryMessagePart


class CreatedAtRangeFilter(admin.SimpleListFilter):
    """Date filter using indexed range lookups instead of aggregate scans.

    The built-in ``DateFieldListFilter`` aggregates over the whole table, which
    is unusable at tens of millions of rows. ``created_at`` is indexed, so
    plain ``gte`` range filters stay fast.
    """

    title: str = "created"
    parameter_name: str = "created"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin):
        return (
            ("1d", "Past 24 hours"),
            ("7d", "Past 7 days"),
            ("30d", "Past 30 days"),
            ("365d", "Past year"),
        )

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        days = {"1d": 1, "7d": 7, "30d": 30, "365d": 365}.get(self.value() or "")
        if days is None:
            return queryset
        return queryset.filter(created_at__gte=timezone.now() - timedelta(days=days))


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
