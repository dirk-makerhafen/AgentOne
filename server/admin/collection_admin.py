"""Admin for DataCollection and CollectionItem models."""
from django.contrib import admin

from server.models.collections import CollectionItem, DataCollection


@admin.register(DataCollection)
class DataCollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "collection_type", "is_active", "item_count", "created_at")
    list_filter = ("collection_type", "is_active")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {
            "fields": ("name", "description", "collection_type", "is_active"),
        }),
        ("Data Flow: Sources", {
            "fields": ("sources",),
            "description": "JSON list of source definitions. "
            "Each source can be a query (project/agent/session/function patterns), "
            "a stream (another stream name), or a set (a set name).",
        }),
        ("Data Flow: Processor", {
            "fields": ("processor",),
            "description": "JSON object with agent, function, and optional session template. "
            "The session template can use {source_agent.name}, {source_session.name}, etc.",
        }),
        ("On-Removed Handler (sets only)", {
            "fields": ("on_removed",),
            "description": "JSON object (same shape as processor) — "
            "runs when items are removed from the source set.",
        }),
        ("Member / Score Extraction (sets only)", {
            "fields": ("member_field", "score_field"),
            "description": "Python expressions evaluated against the item value. "
            "E.g.: member_field=\"item.get('email_id', '')\", score_field=\"item.get('timestamp', 0)\"",
        }),
        ("Reprocess / Backfill", {
            "fields": ("retroactive_on_source_change", "max_reprocess"),
        }),
    )

    @admin.display(description="Items")
    def item_count(self, obj: DataCollection) -> int:
        return obj.items.count()


@admin.register(CollectionItem)
class CollectionItemAdmin(admin.ModelAdmin):
    list_display = ("collection", "member", "score", "source_call", "created_at")
    list_filter = ("collection__collection_type", "collection")
    search_fields = ("member",)
    raw_id_fields = ("source_call",)
    readonly_fields = ("created_at", "updated_at")
