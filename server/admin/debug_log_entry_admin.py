from django.contrib import admin
from server.models.debug_log_entry import DebugLogEntry

@admin.register(DebugLogEntry)
class DebugLogEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'event', 'status', 'created_at')
    list_filter = ('status', 'event', 'created_at')
    search_fields = ('event', 'status', 'session__name')
    autocomplete_fields = ('session',)
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
