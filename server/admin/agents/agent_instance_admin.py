from server.models.sessions.session import SessionModel
from django.contrib import admin

@admin.register(SessionModel)
class AgentInstanceAdmin(admin.ModelAdmin):
    list_display = ("pk", "created_at", 'name',  'latest_session_version', "parent_session")
    list_display_links = ("pk", 'name',"latest_session_version")
    search_fields = ('name',  "latest_session_version")
    list_filter = ( 'created_at',)
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
