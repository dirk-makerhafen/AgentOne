from django.contrib import admin
from common.models import PromptString

@admin.register(PromptString)
class PromptStringAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'owner', 'source', 'key', 'value')
    list_display_links = ('pk', 'owner', 'key')
    search_fields = ('key', 'value', 'owner','source')
    list_per_page = 50
    readonly_fields = ('created_at', 'updated_at')