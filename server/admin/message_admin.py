from django.contrib import admin
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.message import Message
from server.models.message import MessagePart

class ConversationMessagePartInline(admin.TabularInline):
    model = MessagePart
    extra = 0
    fields = ('content_type', "type", 'tokens', 'content', 'template_data')
    #autocomplete_fields = ('content', 'template_data')
    readonly_fields = ('tokens',)


@admin.register(Message)
class ConversationMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_version', 'role', 'source', 'hide_from_context', 'pin_to_context', 'created_at')
    list_display_links = ('id',)
    list_filter = ('role', 'source', 'hide_from_context', 'pin_to_context', 'created_at')
    search_fields = ('id',)
    #autocomplete_fields = (  'query', 'response')
    inlines = [ConversationMessagePartInline]
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25

    fieldsets = (
        ('Conversation Context', {
            'fields': ( 'role', 'source')
        }),
        ('Visibility Settings', {
            'fields': ('hide_from_context', 'pin_to_context'),
            'description': 'Control how this message appears in the model context history.'
        }),
        ('Extended Relations', {
            'fields': ( 'response',),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
