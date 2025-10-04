from django.contrib import admin
from agent.models.agent import Agent, AgentInstance
from agent.models.conversation import ConversationMessage
from agent.models.debug import DebugLogEntry
from agent.models.limits import HistoryLimitingRule
from agent.models.llm import LLMQuery, LLMResponse


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'name', 'description', 'model')
    list_display_links = ('pk', 'name', 'model')
    search_fields = ('name', 'description')
    list_filter = ('model',)
    autocomplete_fields = ('model',)
    filter_horizontal = ('owners',)
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(AgentInstance)
class AgentInstanceAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'name', 'agent', 'system', 'model', 'status')
    list_display_links = ('pk', 'name', 'agent', 'system', 'model')
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('status', 'system', 'agent', 'model')
    search_fields = ('name', 'description', 'agent__name')
    autocomplete_fields = ('agent', 'system', 'model')
    list_per_page = 25

@admin.register(ConversationMessage)
class ConversationMessageAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agentInstance', 'role', 'raw_data')
    list_display_links = ('pk', 'agentInstance')
    list_filter = ('role', 'agentInstance__name', "pin_to_context", "hide_from_context")
    search_fields = ('raw_data', 'agentInstance__name')
    autocomplete_fields = ('agentInstance', 'llmResponse')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(DebugLogEntry)
class DebugLogAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agentInstance', 'event', 'status', 'raw_data')
    list_display_links = ('pk', 'agentInstance')
    list_filter = ('event', 'status', 'agentInstance__name')
    search_fields = ('event', 'raw_data', 'agentInstance__name')
    autocomplete_fields = ('agentInstance',)
    list_per_page = 50
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LLMQuery)
class LLMQueryAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agentInstance', 'model', 'raw_data')
    list_display_links = ('pk', 'agentInstance', 'model')
    list_filter = ('model', 'agentInstance__name')
    search_fields = ('raw_data', 'agentInstance__name')
    autocomplete_fields = ('agentInstance', 'model', 'apikey')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(LLMResponse)
class LLMResponseAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agentInstance', 'llmQuery', 'completion_tokens', 'prompt_tokens', 'raw_data')
    list_display_links = ('pk', 'agentInstance', 'llmQuery')
    list_filter = ('agentInstance__name', 'llmQuery__model__name')
    search_fields = ('raw_data', 'agentInstance__name')
    autocomplete_fields = ('agentInstance', 'llmQuery')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(HistoryLimitingRule)
class HistoryLimitingRuleAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agentInstance', 'group_name', 'rule_name', 'is_active', 'priority', 'limit_success', 'limit_failed', 'limit_max', 'updated_at')
    list_display_links = ('pk', 'group_name', 'rule_name')
    list_filter = ('agentInstance', 'group_name', 'rule_name', 'is_active')
    search_fields = ('group_name', 'rule_name', 'description', 'agentInstance__name')
    autocomplete_fields = ('agentInstance',)
    list_per_page = 50
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = ((None, {'fields': ('agentInstance', 'group_name', 'rule_name', 'description')}), ('Status & Priority', {'fields': ('is_active', 'priority')}), ('Limit Overrides (leave blank to use tool default)', {'fields': ('limit_success', 'limit_failed', 'limit_pending', 'limit_max'), 'classes': ('collapse',)}), ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}))

