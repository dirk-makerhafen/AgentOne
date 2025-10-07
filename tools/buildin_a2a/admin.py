from django.contrib import admin
from tools.buildin_a2a.models.a2a_description import AgentToAgentDescription
from tools.buildin_a2a.models.a2a_message import AgentToAgentMessage
from tools.buildin_a2a.models.a2a_permission import AgentToAgentPermission

@admin.register(AgentToAgentMessage)
class InterAgentMessageAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'sender_agentInstance', 'receiver_agentInstance', 'raw_data')
    list_display_links = ('pk', 'sender_agentInstance', 'receiver_agentInstance')
    readonly_fields = ('created_at',)
    list_filter = ('sender_agentInstance__name', 'receiver_agentInstance__name')
    search_fields = ('sender_agentInstance__name', 'receiver_agentInstance__name', 'data')
    autocomplete_fields = ('sender_agentInstance', 'receiver_agentInstance')
    list_per_page = 25

@admin.register(AgentToAgentDescription)
class AgentInstanceDescriptionLogAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agent_instance', 'description', 'toolCall')
    list_display_links = ('pk', 'agent_instance')
    readonly_fields = ('created_at',)
    list_filter = ('agent_instance__name',)
    search_fields = ('description', 'agent_instance__name')
    autocomplete_fields = ('agent_instance', 'toolCall')
    list_per_page = 50

@admin.register(AgentToAgentPermission)
class InstancePermissionAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'source_instance', 'target_instance', 'can_send', 'can_receive')
    list_display_links = ('pk', 'source_instance', 'target_instance')
    list_filter = ('can_send', 'can_receive')
    search_fields = ('source_instance__name', 'target_instance__name')
    autocomplete_fields = ('source_instance', 'target_instance')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
