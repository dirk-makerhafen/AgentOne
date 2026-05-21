from server.models.queries.query_message import QueryMessage
from django.contrib import admin

@admin.register(QueryMessage)
class QueryMessageAdmin(admin.ModelAdmin):
    search_fields = ('id',)


    list_display = ('id', 'role',  'tokens', 'created_at')
    list_display_links = ('id',)
    list_filter = ('role', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
