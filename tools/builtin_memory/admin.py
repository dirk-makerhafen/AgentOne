from django.contrib import admin
from .models.memory_item import MemoryItem

@admin.register(MemoryItem)
class MemoryItemAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agentInstance', 'track', 'layer', 'index', 'raw_data')
    list_display_links = ('pk', 'track', 'layer')
    list_filter = ('track', 'layer', 'agentInstance__name')
    search_fields = ('track', 'layer', 'raw_data', 'agentInstance__name')
    autocomplete_fields = ('agentInstance', 'next_version')
    list_per_page = 50
    readonly_fields = ('created_at', 'updated_at', 'prev_version', 'next_version')