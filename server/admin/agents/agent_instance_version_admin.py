from server.models.agents.agent_instance_version import InstanceVersionModel
from django.contrib import admin

@admin.register(InstanceVersionModel)
class AgentInstanceVersionAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", 'workingdir', 'agent_instance', 'agent_version')
    list_display_links = ("id", 'agent_instance',)
    search_fields = ('name', 'agent_instance')
    list_filter = ('agent_instance', 'created_at')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('child_agent_instance_versions',)

