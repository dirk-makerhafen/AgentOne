from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from server.models.skills.skill import SkillModel
from api.serializers.skills import (
    SkillListSerializer, SkillDetailSerializer, SkillVersionSerializer,
)


class SkillViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SkillModel.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    filterset_fields = ['name']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return SkillListSerializer
        return SkillDetailSerializer

    @action(detail=True)
    def versions(self, request, pk=None):
        skill = self.get_object()
        try:
            rt = skill.get_runtime() if hasattr(skill, 'get_runtime') else None
        except Exception:
            rt = None
        versions = skill.versions.all().order_by('-version_number')
        serializer = SkillVersionSerializer(versions, many=True)
        return Response(serializer.data)
