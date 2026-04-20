from server.models.queries.query_message_part import QueryMessagePart
from django.contrib import admin

@admin.register(QueryMessagePart)
class QueryMessagePartAdmin(admin.ModelAdmin):
    list_display = ('id', 'query_message', 'content_type', 'index', 'tokens', 'created_at')
    list_display_links = ('id',)
    list_filter = ('content_type', 'created_at')
    search_fields = ('id',)
   
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
