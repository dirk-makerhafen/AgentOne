from rest_framework import viewsets, permissions
from rest_framework.permissions import IsAuthenticated

from server.models.project import Project
from api.serializers.projects import (
    ProjectListSerializer, ProjectDetailSerializer, ProjectWriteSerializer,
)
from api.permissions import IsAdminUserOrReadOnly


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated, IsAdminUserOrReadOnly]
    ordering = ['-created_at']
    filterset_fields = ['name']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectListSerializer
        if self.action in ('create', 'partial_update', 'update'):
            return ProjectWriteSerializer
        return ProjectDetailSerializer
