from django.contrib import admin

from server.models.providers.ai_model import AiModel
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider

@admin.register(ApiProvider)
class ApiProviderAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'name', 'url', 'raw_data')
    list_display_links = ('pk', 'name')
    search_fields = ('name', 'url', 'raw_data')
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'api_provider', 'comment', 'key', 'raw_data')
    list_display_links = ('pk', 'api_provider')
    list_filter = ('api_provider',)
    search_fields = ('comment', 'key', 'raw_data')
    autocomplete_fields = ('api_provider',)
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')

@admin.register(AiModel)
class ModelAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'name', 'api_provider', 'enabled', "vision", "is_cloud","filesize", 'limit_request_per_day', 'limit_request_per_minute', 'limit_tokens_per_day', 'limit_tokens_per_minute', 'raw_data')
    list_display_links = ('pk', 'name', 'api_provider')
    list_filter = ('api_provider', 'enabled')
    search_fields = ('name', 'raw_data')
    autocomplete_fields = ('api_provider',)
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
