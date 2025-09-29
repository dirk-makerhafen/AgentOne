from django.contrib import admin
from .models import FsLogEntry


@admin.register(FsLogEntry)
class FsLogEntryAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agentInstance', 'action', 'path', 'is_newest_version', 'is_pinned','load_mode', 'recursive', 'prev_version',  'content_diff')
    list_display_links = ('pk', 'agentInstance', 'path')
    list_filter = ('action', 'is_pinned', 'load_mode', 'exists_on_fs', 'recursive', 'agentInstance__name')
    search_fields = ('path', 'content_diff', 'agentInstance__name')
    autocomplete_fields = ('agentInstance', 'toolCall', 'prev_version')
    list_per_page = 50
    readonly_fields = ('created_at', 'updated_at', 'prev_version', 'content_diff')
