"""Admin for persistent terminal sessions."""
from django.contrib import admin

from server.models.terminal import TerminalSession


@admin.register(TerminalSession)
class TerminalSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "session", "tmux_session_name", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("name", "tmux_session_name")
