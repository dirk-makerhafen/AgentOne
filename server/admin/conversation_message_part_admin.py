from django.contrib import admin
from server.models.conversation_message_part import ConversationMessagePart

@admin.register(ConversationMessagePart)
class ConversationMessagePartAdmin(admin.ModelAdmin):
    list_display = ('id', 'message_id', 'content_type',  'index', 'tokens', 'created_at','content__content')
    list_filter = ('content_type', 'created_at')
    search_fields = ('id', 'message__id', 'content__content')
    autocomplete_fields = ('message', 'content', 'content_template')
    readonly_fields = ('created_at', 'updated_at', 'tokens')
    list_per_page = 50

    def message_id(self, obj):
        return obj.message.id
    message_id.short_description = 'Message ID'

    fieldsets = (
        (None, {
            'fields': ('message', 'content_type', 'index', 'tokens')
        }),
        ('Content Reference', {
            'fields': ('content', 'content_template'),
            'description': 'References to the polymorphic content storage.'
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
