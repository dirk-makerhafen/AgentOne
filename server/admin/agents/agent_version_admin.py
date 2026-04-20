from django.contrib import admin
from server.models.agents.agent_profile import AgentProfile
from server.models.agents.agent_version import AgentVersion, AgentVersionAvailableTool, AgentVersionSubAgentRelation

class AgentProfileInline(admin.TabularInline):
    
    model = AgentProfile
    extra = 0
    fields = ('name', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True

class AgentVersionAvailableToolInline(admin.TabularInline):
    model = AgentVersionAvailableTool
    extra = 0
    fields = ('created_at',)
    readonly_fields = ('created_at',)
    fk_name = "parent_agent_version"
    show_change_link = True


class AgentVersionSubAgentRelationInline(admin.TabularInline):
    model = AgentVersionSubAgentRelation
    extra = 0
    fk_name = "parent_agent_version"

@admin.register(AgentVersion)
class AgentVersionAdmin(admin.ModelAdmin):
    list_display = ("profile", 'version_number', 'agent',  'created_at')
    list_display_links = ('version_number',)
    search_fields = ('agent__name', 'version_number')
    list_filter = ('agent', 'created_at')
    autocomplete_fields = ('agent',  'profile')
    filter_horizontal = ( 'sub_agent_versions', 'task_definitions')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
    inlines = [AgentVersionAvailableToolInline, AgentVersionSubAgentRelationInline]

    fieldsets = (
        (None, {
            'fields': ('agent', 'version_number')
        }),
        ('Configuration & Logic', {
            'fields': ('source_code', 'profile')
        }),
        ('Resources', {
            'fields': ('sub_agent_versions', 'task_definitions'),
            'description': 'Shared resources and task definitions for this version.'
        }),
        ('Metadata', {
            'fields': ( 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
