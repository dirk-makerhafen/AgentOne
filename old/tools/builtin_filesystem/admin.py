from django.contrib import admin
from .models.fs_log_entry import FsLogEntry

@admin.register(FsLogEntry)
class FsLogEntryAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agent_instance', 'action', 'path', 'is_newest_version', 'is_pinned','load_mode', 'recursive', 'prev_version',  'content_diff')
    list_display_links = ('pk', 'agent_instance', 'path')
    list_filter = ('action', 'is_pinned', 'load_mode', 'exists_on_fs', 'recursive', 'agent_instance__name')
    search_fields = ('path', 'content_diff', 'agent_instance__name')
    autocomplete_fields = ('agent_instance',  'prev_version')
    list_per_page = 50
    readonly_fields = ('created_at', 'updated_at', 'prev_version', 'content_diff')
