from django.contrib import admin
from .models import ApiProvider, ApiKey, Model

@admin.register(ApiProvider)
class ApiProviderAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'name', 'url', 'raw_data')
    list_display_links = ('pk', 'name')
    search_fields = ('name', 'url', 'raw_data')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'apiProvider', 'comment', 'key', 'raw_data')
    list_display_links = ('pk', 'apiProvider')
    list_filter = ('apiProvider',)
    search_fields = ('comment', 'key', 'raw_data')
    autocomplete_fields = ('apiProvider',)
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Model)
class ModelAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'name', 'apiProvider', 'enabled', 'max_tokens', 'free_limit_per_day', 'raw_data')
    list_display_links = ('pk', 'name', 'apiProvider')
    list_filter = ('apiProvider', 'enabled')
    search_fields = ('name', 'raw_data')
    autocomplete_fields = ('apiProvider',)
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
