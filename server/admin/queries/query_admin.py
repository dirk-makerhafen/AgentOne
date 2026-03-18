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
    fields = ('status', 'aimodel', 'prompt_tokens', 'completion_tokens', 'created_at')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('aimodel',)

 

@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ('id', 'agent_instance_version', 'status', 'tokens', 'created_at', 'agent_profile')
    list_display_links = ('id',)
    list_filter = ('status', 'aimodel', 'agent_instance_version__agent', 'created_at')
    search_fields = ('id', 'agent_instance_version__name')
    autocomplete_fields = ('aimodel', 'apikey',   'agent_profile', 'agent_instance_version')
    readonly_fields = ('created_at', 'updated_at', 'tokens', 'tags_token_usage')
    inlines = [QueryMessageInline, ResponseInline]
    list_per_page = 25

    fieldsets = (
        (None, {
            'fields': ('agent_instance_version', 'status', 'aimodel', 'apikey')
        }),
        ('Tracking & Usage', {
            'fields': ('tokens', 'tags_token_usage'),
            'classes': ('collapse',)
        }),
        ('Entity Snapshot', {
            'fields': ( 'agent_profile',),
            'classes': ('collapse',)
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
