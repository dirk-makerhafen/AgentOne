"""Admin for the Message model (formerly ConversationMessage)."""
from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from server.models.message import Message, MessagePart


class MessagePartInline(admin.TabularInline):
    """Inline editor for message parts attached to a message."""

    model: type[MessagePart] = MessagePart
    extra: int = 0
    fields: tuple[str, ...] = ("content_type", "type", "tokens", "content", "template_data")
    readonly_fields: tuple[str, ...] = ("tokens",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Admin for conversation messages."""

    list_display: tuple[str, ...] = (
        "id", "session_version", "role", "source",
        "hide_from_context", "pin_to_context", "created_at", "prev_message",
    )
    list_display_links: tuple[str, ...] = ("id",)
    list_filter: tuple[str, ...] = (
        "role", "source", "hide_from_context", "pin_to_context", "created_at",
    )
    search_fields: tuple[str, ...] = ("id",)
    inlines: list[type[admin.TabularInline]] = [MessagePartInline]
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
    list_per_page: int = 25

    fieldsets: tuple[tuple[str, dict[str, Any]], ...] = (
        ("Conversation Context", {
            "fields": ("role", "source"),
        }),
        ("Visibility Settings", {
            "fields": ("hide_from_context", "pin_to_context"),
            "description": "Control how this message appears in the model context history.",
        }),
        ("Extended Relations", {
            "fields": ("response","prev_message"),
            "classes": ("collapse",),
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
