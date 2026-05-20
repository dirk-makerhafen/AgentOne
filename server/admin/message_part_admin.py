from django.contrib import admin
from server.models.message import MessagePart

@admin.register(MessagePart)
class ConversationMessagePartAdmin(admin.ModelAdmin):
    list_display = ('id', 'message_id', 'content_type', "type", 'index', 'tokens', 'created_at','content__content','tool_call')
    list_filter = ('content_type', 'created_at')
    search_fields = ('id',)
    readonly_fields = ('created_at', 'updated_at', 'tokens')
    list_per_page = 50

    def message_id(self, obj):
        return obj.message.id
    message_id.short_description = 'Message ID'

    fieldsets = (
        (None, {
            'fields': ('message', 'content_type', 'index', 'tokens', "tool_call")
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
