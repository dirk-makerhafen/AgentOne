from server.models.queries.query_message_part import QueryMessagePart
from django.contrib import admin

@admin.register(QueryMessagePart)
class QueryMessagePartAdmin(admin.ModelAdmin):
    list_display = ('id', 'query_message', 'content_type', 'index', 'tokens', 'created_at')
    list_display_links = ('id',)
    list_filter = ('content_type', 'created_at')
    search_fields = ('id', 'query_message__id')
    autocomplete_fields = (
        'query_message', 'conversation_message', 'conversation_message_part', 
         'content', 'content_prefix', 'content_postfix', 'content_template'
    )
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
