from django.contrib import admin
from server.models.agents.agent import Agent
from server.models.agents.agent_version import AgentVersion

class AgentVersionInline(admin.TabularInline):
    model = AgentVersion
    extra = 0
    fields = ('version_number', 'created_at')
    readonly_fields = ('version_number', 'created_at')
    show_change_link = True
    can_delete = False

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('name',  'created_at', 'updated_at')
    list_display_links = ('name',)
    list_filter = ( 'created_at', )
    search_fields = ('name', 'description')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
    inlines = [AgentVersionInline]
    
    fieldsets = (
        (None, {
            'fields': ('name', 'description')
        }),
        ('System Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
