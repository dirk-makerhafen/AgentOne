from django.contrib import admin

from providers.models.ai_model import AiModel
from providers.models.api_key import ApiKey
from providers.models.api_provider import ApiProvider

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

@admin.register(AiModel)
class ModelAdmin(admin.ModelAdmin):
    list_display = ('pk', 'created_at', 'name', 'apiProvider', 'enabled', 'max_prompt_tokens', 'limit_request_per_day', 'limit_request_per_minute', 'limit_tokens_per_day', 'limit_tokens_per_minute', 'raw_data')
    list_display_links = ('pk', 'name', 'apiProvider')
    list_filter = ('apiProvider', 'enabled')
    search_fields = ('name', 'raw_data')
    autocomplete_fields = ('apiProvider',)
    list_per_page = 25
    readonly_fields = ('created_at', 'updated_at')
