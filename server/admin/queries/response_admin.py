from django.contrib import admin
from server.models.queries.response import Response

@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('id', 'query', 'aimodel', 'agent_instance_version__agent', 'agent_instance_version__agent_version', 'status', 'prompt_tokens', 'completion_tokens', 'status', 'created_at')
    list_display_links = ('id',)
    list_filter = ('status', 'aimodel')
    autocomplete_fields = ( 'aimodel', )
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
