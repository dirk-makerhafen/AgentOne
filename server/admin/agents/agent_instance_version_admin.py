from server.models.sessions.session_version import SessionVersionModel
from django.contrib import admin

@admin.register(SessionVersionModel)
class AgentInstanceVersionAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", 'workingdir', 'session')
    list_display_links = ("id", 'session',)
    search_fields = ('name', 'session')
    list_filter = ('session', 'created_at')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('child_session_versions',)

