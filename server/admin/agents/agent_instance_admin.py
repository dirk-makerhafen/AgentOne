from server.models.agents.agent_instance import AgentInstance
from django.contrib import admin

@admin.register(AgentInstance)
class AgentInstanceAdmin(admin.ModelAdmin):
    list_display = ("pk", "created_at", 'name', 'agent', 'latest_agent_instance_version', "parent")
    list_display_links = ("pk", 'name', "agent" ,"latest_agent_instance_version")
    search_fields = ('name', 'agent', "latest_agent_instance_version")
    list_filter = ('agent', 'created_at')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
