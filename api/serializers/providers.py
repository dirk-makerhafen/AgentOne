from rest_framework import serializers
from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel
from server.models.providers.api_key import ApiKey


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = ['id', 'comment', 'enabled', 'limit_request_per_day',
                  'limit_request_per_minute', 'created_at']
        read_only_fields = ['key']


class AiModelListSerializer(serializers.ModelSerializer):
    provider_name = serializers.SerializerMethodField()

    class Meta:
        model = AiModel
        fields = ['id', 'name', 'family', 'provider_name', 'enabled',
                  'context_length', 'vision', 'self_hosted',
                  'total_parameters', 'active_parameters', 'quantization',
                  'created_at', 'updated_at']

    def get_provider_name(self, obj) -> str | None:
        return obj.api_provider.name if obj.api_provider else None


class AiModelDetailSerializer(serializers.ModelSerializer):
    provider = serializers.SerializerMethodField()

    class Meta:
        model = AiModel
        fields = ['id', 'name', 'family', 'provider', 'description',
                  'enabled', 'context_length', 'is_cloud', 'self_hosted',
                  'vision', 'total_parameters', 'active_parameters',
                  'quantization',
                  'max_prompt_tokens', 'max_response_tokens',
                  'limit_request_per_day', 'limit_request_per_minute',
                  'limit_tokens_per_day', 'limit_tokens_per_minute',
                  'limit_parallel_calls',
                  'created_at', 'updated_at']

    def get_provider(self, obj) -> dict | None:
        return {'id': obj.api_provider_id, 'name': obj.api_provider.name} if obj.api_provider else None


class ProviderListSerializer(serializers.ModelSerializer):
    model_count = serializers.SerializerMethodField()
    key_count = serializers.SerializerMethodField()

    class Meta:
        model = ApiProvider
        fields = ['id', 'name', 'url', 'model_count', 'key_count',
                  'limit_parallel_calls', 'created_at', 'updated_at']

    def get_model_count(self, obj) -> int:
        return obj.aimodels.count()

    def get_key_count(self, obj) -> int:
        return obj.api_keys.count()


class ProviderDetailSerializer(serializers.ModelSerializer):
    models = AiModelListSerializer(many=True, read_only=True, source='aimodels')
    keys = ApiKeySerializer(many=True, read_only=True, source='api_keys')

    class Meta:
        model = ApiProvider
        fields = ['id', 'name', 'url', 'models', 'keys',
                  'limit_parallel_calls', 'created_at', 'updated_at']
