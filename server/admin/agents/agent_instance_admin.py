from server.models.agents.agent_instance import InstanceModel
from django.contrib import admin

@admin.register(InstanceModel)
class AgentInstanceAdmin(admin.ModelAdmin):
    list_display = ("pk", "created_at", 'name', 'agent', 'latest_instance_version', "created_by")
    list_display_links = ("pk", 'name', "agent" ,"latest_instance_version")
    search_fields = ('name', 'agent', "latest_instance_version")
    list_filter = ('agent', 'created_at')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
