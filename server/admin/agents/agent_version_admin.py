from django.contrib import admin
from server.models.agents.profile import ProfileModel
from server.models.agents.agent_version import AgentVersionModel


class AgentProfileInline(admin.TabularInline):
    
    model = ProfileModel
    extra = 0
    fields = ('name', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True

@admin.register(AgentVersionModel)
class AgentVersionAdmin(admin.ModelAdmin):
    list_display = ( 'version_number', 'agent',  'created_at')
    list_display_links = ('version_number',)
    list_filter = ('agent', 'created_at')
    #filter_horizontal = ( 'sub_agent_versions', )
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('agent', 'version_number')
        }),
        
        ('Metadata', {
            'fields': ( 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
