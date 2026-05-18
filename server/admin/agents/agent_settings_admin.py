from server.models.settings import SettingsModel
from django.contrib import admin

@admin.register(SettingsModel)
class AgentProfileAdmin(admin.ModelAdmin):
    
    list_display = ('aimodel', 'execution_mode', 'created_at')
    search_fields = ('aimodel__name', 'execution_mode')
    list_filter = ('aimodel', 'execution_mode', 'created_at')
    autocomplete_fields = ('aimodel',)
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
