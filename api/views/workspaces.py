from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from server.models.workspace import WorkspaceModel
from api.serializers.workspaces import (
    WorkspaceListSerializer, WorkspaceDetailSerializer, WorkspaceWriteSerializer,
)
from api.permissions import IsAdminUserOrReadOnly


class WorkspaceViewSet(viewsets.ModelViewSet):
    queryset = WorkspaceModel.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated, IsAdminUserOrReadOnly]
    ordering = ['-created_at']
    filterset_fields = ['name']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return WorkspaceListSerializer
        if self.action in ('create', 'partial_update', 'update'):
            return WorkspaceWriteSerializer
        return WorkspaceDetailSerializer
