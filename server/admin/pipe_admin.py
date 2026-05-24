"""Admin for NamedPipe and NamedPipeSubscription models."""
from django.contrib import admin

from server.models.pipe import NamedPipe, NamedPipeSubscription


@admin.register(NamedPipe)
class NamedPipeAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "subscription_count", "created_at")
    search_fields = ("name", "description")

    @admin.display(description="Consumers")
    def subscription_count(self, obj: NamedPipe) -> int:
        return obj.subscriptions.count()


@admin.register(NamedPipeSubscription)
class NamedPipeSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("name", "pipe", "consumer_task", "agent", "session_mode", "is_active", "created_at")
    list_filter = ("is_active", "pipe", "session_mode")
    search_fields = ("name",)
    raw_id_fields = ("pipe", "consumer_task", "agent")
