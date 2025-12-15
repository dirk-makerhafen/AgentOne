from django.contrib import admin
from .models.agent import Agent
from .models.agent_instance import AgentInstance, AgentTask
from .models.conversation_message import ConversationMessage, ConversationMessagePart
from .models.debug_log_entry import DebugLogEntry
from .models.history_limit import HistoryLimit
from .models.llm_query import LLMQuery, QueryMessage, QueryMessagePart
from .models.llm_response import LLMResponse
from .models.agent_instance_fork import AgentInstanceFork
from .models.query_queue import QueryQueue
from .models.sub_agent_link import SubAgentLink

# --- Inlines for nested structures ---
@admin.register(AgentTask)
class AgentTaskAdmin(admin.ModelAdmin):
     list_display = ('agent', 'agentInstance', 'status', 'arguments', 'result', 'raw_data')


class ConversationMessagePartInline(admin.TabularInline):
    model = ConversationMessagePart
    extra = 0
    # Corrected fields based on the ConversationMessagePart model
    fields = ('index', 'content', 'tokens')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('index',)

class QueryMessagePartInline(admin.TabularInline):
    model = QueryMessagePart
    extra = 0
    # These fields are correct for the QueryMessagePart model
    fields = ('index', 'content', 'tokens', 'tags', 'promptVariant', 'conversationMessagePart')
    autocomplete_fields = ( 'promptVariant', 'conversationMessagePart')
    readonly_fields = ('created_at', 'updated_at','conversationMessagePart')
    ordering = ('index',)

class QueryMessageInline(admin.TabularInline):
    model = QueryMessage
    extra = 0
    inlines = [QueryMessagePartInline]
    fields = ('index', 'role', 'tokens', 'content_prefix', 'content_postfix')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('index',)


# --- Model Admins ---

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('agent_pk', 'created_at', 'name', 'description', 'aimodel')
    list_display_links = ('agent_pk', 'name')
    search_fields = ('name', 'description')
    list_filter = ('aimodel',)
    autocomplete_fields = ('aimodel',)
    filter_horizontal = ('owners', "available_tools")
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(AgentInstance)
class AgentInstanceAdmin(admin.ModelAdmin):
    list_display = ('instance_pk', 'created_at', 'name', 'agent', 'system', 'aimodel', 'status')
    list_display_links = ('instance_pk', 'name', 'agent')
    fieldsets = (
        (None, {
            'fields': ('agent', 'system', 'aimodel', 'name', 'description_text', 'status', 'workingdir', 'require_user_interaction', 'workingdir_write_allowed', 'access_rules', 'parent')
        }),
        ('Rate Limiting', {
            'fields': ('max_requests_per_minute', 'max_token_per_minute'),
            'description': 'Set instance-specific rate limits. If null, limits are inherited from the parent agent.'
        }),
        ('Limits Overrides', {
            'fields': ('limit_max_conversation_messages', 'limit_max_memory_items', 'limit_max_automated_steps'),
            'classes': ('collapse',)
        }),
        # Forking fields removed as they are now handled by AgentInstanceFork
        ('History', {
            'fields': ('automated_step_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('status', 'system', 'agent', 'aimodel')
    search_fields = ('name', 'description_text', 'agent__name')
    autocomplete_fields = ('agent', 'system', 'aimodel')
    list_per_page = 25

@admin.register(ConversationMessage)
class ConversationMessageAdmin(admin.ModelAdmin):
    inlines = [ConversationMessagePartInline]
    list_display = ('pk', 'created_at', 'agentInstance', 'role', 'hide_from_context', 'pin_to_context')
    list_display_links = ('pk', 'agentInstance')
    list_filter = ('role', 'agentInstance__name', "pin_to_context", "hide_from_context")
    search_fields = ('conversationMessageParts__content', 'agentInstance__name')
    autocomplete_fields = ('agentInstance', 'llmResponse')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ConversationMessagePart)
class ConversationMessagePartAdmin(admin.ModelAdmin):
    list_display = ('pk', 'conversationMessage', 'index', 'content')
    list_display_links = ('pk',)
    search_fields = ('content',)

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
    inlines = [QueryMessageInline]
    list_display = ('pk', 'created_at', 'agentInstance', 'aimodel', 'status', 'tokens')
    list_display_links = ('pk', 'agentInstance')
    list_filter = ('status', 'aimodel', 'agentInstance__name')
    search_fields = ('agentInstance__name',)
    autocomplete_fields = ('agentInstance', 'aimodel', 'apikey')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(QueryMessage)
class QueryMessageAdmin(admin.ModelAdmin):
    inlines = [QueryMessagePartInline]
    list_display = ('pk', 'llmQuery', 'role', 'index', 'tokens')
    list_display_links = ('pk',)
    autocomplete_fields = ('llmQuery',)
    # Added search_fields to satisfy the admin check dependency
    search_fields = ('llmQuery__agentInstance__name', 'role')

@admin.register(QueryMessagePart)
class QueryMessagePartAdmin(admin.ModelAdmin):
    list_display = ('pk', 'queryMessage', 'index', 'tokens', 'content', "conversationMessage", "conversationMessagePart")
    list_display_links = ('pk',)
    # These autocomplete fields are correct for this model
    readonly_fields = ('queryMessage','promptVariant', 'conversationMessagePart')

@admin.register(LLMResponse)
class LLMResponseAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agentInstance', 'llmQuery', 'status', 'completion_tokens', 'prompt_tokens')
    list_display_links = ('pk', 'agentInstance', 'llmQuery')
    list_filter = ('status', 'agentInstance__name', 'llmQuery__aimodel__name')
    search_fields = ('raw_data', 'agentInstance__name')
    autocomplete_fields = ('agentInstance', 'llmQuery')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(HistoryLimit)
class HistoryLimitAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agent', 'group_name', 'rule_name', 'is_active', 'priority', 'limit_success', 'limit_failed', 'limit_max')
    list_display_links = ('pk', 'group_name', 'rule_name')
    list_filter = ('agent', 'group_name', 'rule_name', 'is_active')
    search_fields = ('group_name', 'rule_name', 'description', 'agent__name')
    autocomplete_fields = ('agent',)
    list_per_page = 50
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = ((None, {'fields': ('agent', 'group_name', 'rule_name', 'description')}), ('Status & Priority', {'fields': ('is_active', 'priority')}), ('Limit Overrides (leave blank to use tool default)', {'fields': ('limit_success', 'limit_failed', 'limit_pending', 'limit_max'), 'classes': ('collapse',)}), ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}))

@admin.register(AgentInstanceFork)
class AgentInstanceForkAdmin(admin.ModelAdmin):
    list_display = ('id', 'parent_instance', 'child_instance', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('parent_instance__name', 'child_instance__name')
    autocomplete_fields = ('parent_instance', 'child_instance')

@admin.register(QueryQueue)
class QueryQueueAdmin(admin.ModelAdmin):
    list_display = ('agent_instance', 'status', 'created_at')
    list_display_links = ('agent_instance',)
    list_filter = ('status',)
    search_fields = ('agent_instance__name',)
    autocomplete_fields = ('agent_instance',)
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 50

@admin.register(SubAgentLink)
class SubAgentLinkAdmin(admin.ModelAdmin):
    list_display = ('id', 'supervisor_instance', 'subordinate_instance', 'created_at')
    search_fields = ('supervisor_instance__name', 'subordinate_instance__name')
    autocomplete_fields = ('supervisor_instance', 'subordinate_instance')

