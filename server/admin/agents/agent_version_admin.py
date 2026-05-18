from django.contrib import admin
from server.models.settings import SettingsModel
from server.models.agents.agent_version import AgentVersionModel


class AgentProfileInline(admin.TabularInline):
    
    model = SettingsModel
    extra = 0
    fields = ('name', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True

@admin.register(AgentVersionModel)
class AgentVersionAdmin(admin.ModelAdmin):
    list_display = ( 'version_number', 'agent',  'created_at')
    list_display_links = ('version_number',)
     