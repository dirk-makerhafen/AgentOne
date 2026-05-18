from django.contrib import admin
from server.models.queries.query import Query
from server.models.queries.query_message import QueryMessage
from server.models.queries.response import Response

class QueryMessageInline(admin.TabularInline):
    model = QueryMessage
    extra = 0
    fields = ('index', 'role', 'tokens')
    readonly_fields = ('tokens',)
    show_change_link = True

class ResponseInline(admin.StackedInline):
    model = Response
    extra = 0
    can_delete = False
    fields = ('status',  'prompt_tokens', 'completion_tokens', 'created_at')
    readonly_fields = ('created_at',)
    autocomplete_fields = ()

 

@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ('id', 'session_version', 'status', 'tokens', 'created_at')
    list_display_links = ('id',)
    list_filter = ('status',  'session_version__agent', 'created_at')
    search_fields = ('id', 'session_version__name')
    autocomplete_fields = ( 'apikey', 'session_version')
    readonly_fields = ('created_at', 'updated_at', 'tokens', 'tags_token_usage')
    inlines = [QueryMessageInline, ResponseInline]
    list_per_page = 25

    fieldsets = (
        (None, {
            'fields': ('session_version', 'status',  'apikey')
        }),
        ('Tracking & Usage', {
            'fields': ('tokens', 'tags_token_usage'),
            'classes': ('collapse',)
        }),
        
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
