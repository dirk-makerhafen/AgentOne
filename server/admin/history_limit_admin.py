from django.contrib import admin
from server.models.history_limit import HistoryLimitingRule

@admin.register(HistoryLimitingRule)
class HistoryLimitAdmin(admin.ModelAdmin):
    list_display = ('rule_name', 'agent', 'group_name',)
    list_filter = ( 'group_name', 'agent', 'created_at')
    search_fields = ('rule_name', 'group_name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 25
