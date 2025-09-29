from django.contrib import admin
from .models import PythonToolVar

@admin.register(PythonToolVar)
class PythonToolVarAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'agentInstance', 'key', 'raw_data')
    list_display_links = ('pk', 'key')
    list_filter = ('agentInstance',)
    search_fields = ('key', 'data')
    autocomplete_fields = ('agentInstance',)
    readonly_fields = ('created_at', 'updated_at', 'prev_version', 'next_version')
