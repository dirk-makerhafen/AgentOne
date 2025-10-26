from django.contrib import admin
from .models.kv_item import KVItem

@admin.register(KVItem)
class KVItemAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'agent', 'created_at')
    search_fields = ('key', 'value')
    list_filter = ('agent', 'created_at')