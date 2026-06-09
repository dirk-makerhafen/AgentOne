from rest_framework import viewsets, permissions
from rest_framework.permissions import IsAuthenticated

from server.models.providers.api_provider import ApiProvider
from server.models.providers.ai_model import AiModel
from api.serializers.providers import (
    ProviderListSerializer, ProviderDetailSerializer,
    AiModelListSerializer, AiModelDetailSerializer,
)
from api.permissions import IsAdminUserOrReadOnly


class ProviderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ApiProvider.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated, IsAdminUserOrReadOnly]
    ordering = ['-created_at']
    filterset_fields = ['name']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProviderListSerializer
        return ProviderDetailSerializer


class AiModelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AiModel.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated, IsAdminUserOrReadOnly]
    ordering = ['-created_at']
    filterset_fields = ['name', 'family', 'enabled', 'api_provider']
    search_fields = ['name', 'family']

    def get_serializer_class(self):
        if self.action == 'list':
            return AiModelListSerializer
        return AiModelDetailSerializer
