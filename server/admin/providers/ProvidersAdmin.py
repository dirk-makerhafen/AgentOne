"""Admin for provider models (ApiProvider, ApiKey, AiModel)."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.providers.ai_model import AiModel
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider


@admin.register(ApiProvider)
class ApiProviderAdmin(admin.ModelAdmin):
    """Admin for API provider configurations."""

    list_display: tuple[str, ...] = ("pk", "created_at", "name", "url", "raw_data")
    list_display_links: tuple[str, ...] = ("pk", "name")
    search_fields: tuple[str, ...] = ("name", "url", "raw_data")
    list_per_page: int = 25
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    """Admin for API keys."""

    list_display: tuple[str, ...] = (
        "pk", "created_at", "api_provider", "comment", "key", "raw_data",
    )
    list_display_links: tuple[str, ...] = ("pk", "api_provider")
    list_filter: tuple[str, ...] = ("api_provider",)
    search_fields: tuple[str, ...] = ("comment", "key", "raw_data")
    autocomplete_fields: tuple[str, ...] = ("api_provider",)
    list_per_page: int = 25
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")


@admin.register(AiModel)
class ModelAdmin(admin.ModelAdmin):
    """Admin for AI model definitions."""

    list_display: tuple[str, ...] = (
        "pk", "created_at", "name", "provider_model_id", "api_provider", "enabled", "vision",
        "open_weights", "supports_reasoning", "supports_tool_call",
        "total_parameters", "active_parameters", "quantization",
        "is_cloud", "filesize", "limit_request_per_day",
        "limit_request_per_minute", "limit_tokens_per_day",
        "limit_tokens_per_minute", "raw_data",
    )
    list_display_links: tuple[str, ...] = ("pk", "name", "api_provider")
    list_filter: tuple[str, ...] = ("api_provider", "enabled")
    search_fields: tuple[str, ...] = ("name", "raw_data")
    autocomplete_fields: tuple[str, ...] = ("api_provider",)
    list_per_page: int = 25
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
