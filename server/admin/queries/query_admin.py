"""Admin for the Query, QueryMessage, and Response models."""
from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from server.models.queries.query import Query
from server.models.queries.query_message import QueryMessage
from server.models.queries.response import Response


class QueryMessageInline(admin.TabularInline):
    """Inline editor for query messages."""

    model: type[QueryMessage] = QueryMessage
    extra: int = 0
    fields: tuple[str, ...] = ("index", "role", "tokens")
    readonly_fields: tuple[str, ...] = ("tokens",)
    show_change_link: bool = True


class ResponseInline(admin.StackedInline):
    """Inline editor for query responses."""

    model: type[Response] = Response
    extra: int = 0
    can_delete: bool = False
    fields: tuple[str, ...] = ("status", "prompt_tokens", "completion_tokens", "created_at")
    readonly_fields: tuple[str, ...] = ("created_at",)


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    """Admin for LLM query records."""

    list_display: tuple[str, ...] = (
        "id", "session_version", "status", "tokens", "created_at",
    )
    list_display_links: tuple[str, ...] = ("id",)
    list_filter: tuple[str, ...] = ("status", "session_version__agent", "created_at")
    search_fields: tuple[str, ...] = ("id", "session_version__name")
    autocomplete_fields: tuple[str, ...] = ("apikey", "session_version")
    readonly_fields: tuple[str, ...] = (
        "created_at", "updated_at", "tokens", "tags_token_usage",
    )
    inlines: list[type] = [QueryMessageInline, ResponseInline]
    list_per_page: int = 25

    fieldsets: tuple[tuple[str, dict[str, Any]], ...] = (
        (None, {
            "fields": ("session_version", "status", "apikey"),
        }),
        ("Tracking & Usage", {
            "fields": ("tokens", "tags_token_usage"),
            "classes": ("collapse",),
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
