from django.contrib import admin
from .models.kv_item import KVItem

@admin.register(KVItem)
class KVItemAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'agentInstance', 'created_at')
    search_fields = ('key', 'value')
    list_filter = ('agentInstance', 'created_at')