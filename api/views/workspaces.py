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

    def perform_create(self, serializer):
        from runtime.events import publish_model_event

        instance = serializer.save()
        publish_model_event(instance, "create")

    def perform_update(self, serializer):
        from runtime.events import publish_model_event

        instance = serializer.save()
        publish_model_event(instance, "update")

    def perform_destroy(self, instance):
        from runtime.events import publish_model_event

        super().perform_destroy(instance)
        publish_model_event(instance, "delete")
