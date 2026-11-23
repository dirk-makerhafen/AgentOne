"""Admin for the MessagePart model (formerly ConversationMessagePart)."""
from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from server.admin.filters import CreatedAtRangeFilter
from server.models.message import MessagePart


@admin.register(MessagePart)
class MessagePartAdmin(admin.ModelAdmin):
    """Admin for individual parts of a conversation message."""

    list_display: tuple[str, ...] = (
        "id", "message_id", "content_type", "type", "tokens",
        "created_at", "content__content", "tool_call",
    )
    list_filter: tuple[str, ...] = ("content_type", CreatedAtRangeFilter)
    search_fields: tuple[str, ...] = ("id",)
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at", "tokens")
    # Django's default (False) would call select_related() with no arguments
    # because list_display contains relations, dragging in the whole
    # message -> session -> session_version -> agent graph and forcing a
    # filesort over the huge MessagePart table just to render 50 rows.
    list_select_related: tuple[str, ...] = ("message", "tool_call__task_definition")
    list_per_page: int = 50
    show_full_result_count: bool = False

    fieldsets: tuple[tuple[str, dict[str, Any]], ...] = (
        (None, {
            "fields": ("message", "content_type", "tokens", "tool_call"),
        }),
        ("Content Reference", {
            "fields": ("content", "template_data"),
            "description": "References to the polymorphic content storage.",
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def message_id(self, obj: MessagePart) -> int:
        """Return the parent message ID for display."""
        return obj.message.id

    message_id.short_description = "Message ID"  # type: ignore[attr-defined]
