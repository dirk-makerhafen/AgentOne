"""Admin for provider models (ApiProvider, ApiKey, AiModel)."""
from django.contrib import admin
from django.http import HttpRequest

from server.models.providers.ai_model import AiModel
from server.models.providers.ai_model_offering import AiModelOffering
from server.models.providers.api_key import ApiKey
from server.models.providers.api_provider import ApiProvider


@admin.register(ApiProvider)
class ApiProviderAdmin(admin.ModelAdmin):
    """Admin for API provider configurations."""

    list_display: tuple[str, ...] = ("pk", "created_at", "name", "url")
    list_display_links: tuple[str, ...] = ("pk", "name")
    search_fields: tuple[str, ...] = ("name", "url", "description")
    list_per_page: int = 25
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    """Admin for API keys."""

    list_display: tuple[str, ...] = (
        "pk", "created_at", "api_provider", "comment", "key",
    )
    list_display_links: tuple[str, ...] = ("pk", "api_provider")
    list_filter: tuple[str, ...] = ("api_provider",)
    search_fields: tuple[str, ...] = ("comment", "key")
    autocomplete_fields: tuple[str, ...] = ("api_provider",)
    list_per_page: int = 25
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")


@admin.register(AiModelOffering)
class ModelAdmin(admin.ModelAdmin):
    """Admin for AI model offerings (provider ↔ model)."""

    list_display: tuple[str, ...] = (
        "pk", "created_at", "name", "provider_model_id", "api_provider", "enabled", "vision",
        "open_weights", "supports_reasoning", "supports_tool_call",
        "total_parameters", "active_parameters", "quantization",
        "is_cloud", "filesize", "limit_request_per_day",
        "limit_request_per_minute", "limit_tokens_per_day",
        "limit_tokens_per_minute", "conditions",
    )
    list_display_links: tuple[str, ...] = ("pk", "name", "api_provider")
    list_filter: tuple[str, ...] = ("api_provider", "enabled")
    search_fields: tuple[str, ...] = ("name", "description", "provider_model_id")
    autocomplete_fields: tuple[str, ...] = ("api_provider", "model")
    list_per_page: int = 25
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")


@admin.register(AiModel)
class RawModelAdmin(admin.ModelAdmin):
    """Admin for raw (provider-independent) AI models."""

    list_display: tuple[str, ...] = (
        "pk", "created_at", "name", "developer", "canonical_id",
        "context_length", "max_output_tokens", "open_weights",
        "supports_reasoning", "supports_tool_call",
    )
    list_display_links: tuple[str, ...] = ("pk", "name")
    search_fields: tuple[str, ...] = ("name", "developer", "canonical_id")
    list_per_page: int = 25
    readonly_fields: tuple[str, ...] = ("created_at", "updated_at")
