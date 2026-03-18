from server.models.agents.agent_instance_version import AgentInstanceVersion
from django.contrib import admin

@admin.register(AgentInstanceVersion)
class AgentInstanceVersionAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", 'workingdir', 'agent_instance', 'agent_version', 'pinned_agent_profile')
    list_display_links = ("id", 'agent_instance',)
    search_fields = ('name', 'agent_instance')
    list_filter = ('agent_instance', 'created_at')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('child_agent_instance_versions',)

