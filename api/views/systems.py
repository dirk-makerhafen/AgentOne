from rest_framework import viewsets, permissions
from rest_framework.permissions import IsAuthenticated

from server.models.system import System
from api.serializers.systems import (
    SystemListSerializer, SystemDetailSerializer, SystemWriteSerializer,
)
from api.permissions import IsAdminUserOrReadOnly


class SystemViewSet(viewsets.ModelViewSet):
    queryset = System.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated, IsAdminUserOrReadOnly]
    ordering = ['-created_at']
    filterset_fields = ['name', 'status', 'os']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return SystemListSerializer
        if self.action in ('partial_update', 'update'):
            return SystemWriteSerializer
        return SystemDetailSerializer
