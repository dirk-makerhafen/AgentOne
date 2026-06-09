from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from server.models.agents.agent import AgentModel
from api.serializers.agents import (
    AgentListSerializer, AgentDetailSerializer, AgentWriteSerializer,
    AgentVersionSerializer, TaskDefinitionVersionSerializer,
    SkillVersionRefSerializer,
)


class AgentViewSet(viewsets.ModelViewSet):
    queryset = AgentModel.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    filterset_fields = ['name']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return AgentListSerializer
        if self.action in ('create', 'partial_update', 'update'):
            return AgentWriteSerializer
        return AgentDetailSerializer

    @action(detail=True)
    def commands(self, request, pk=None):
        agent = self.get_object()
        try:
            rt = agent.get_runtime()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = TaskDefinitionVersionSerializer(rt.allowedCommands, many=True)
        return Response(serializer.data)

    @action(detail=True)
    def tasks(self, request, pk=None):
        agent = self.get_object()
        try:
            rt = agent.get_runtime()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = TaskDefinitionVersionSerializer(rt.allowedTasks, many=True)
        return Response(serializer.data)

    @action(detail=True)
    def tools(self, request, pk=None):
        agent = self.get_object()
        try:
            rt = agent.get_runtime()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = TaskDefinitionVersionSerializer(rt.allowedTools, many=True)
        return Response(serializer.data)

    @action(detail=True)
    def skills(self, request, pk=None):
        agent = self.get_object()
        try:
            rt = agent.get_runtime()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = SkillVersionRefSerializer(rt.allowedSkills, many=True)
        return Response(serializer.data)

    @action(detail=True)
    def subagents(self, request, pk=None):
        agent = self.get_object()
        try:
            rt = agent.get_runtime()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        data = []
        for sa in rt.allowedSubagents:
            config = rt.subagent_config(sa.agent.name)
            data.append({
                'id': sa.id,
                'name': sa.agent.name,
                'version_number': sa.version_number,
                'config': config,
            })
        return Response(data)

    @action(detail=True)
    def versions(self, request, pk=None):
        agent = self.get_object()
        versions = agent.related_agent_versions.all().order_by('-version_number')
        serializer = AgentVersionSerializer(versions, many=True)
        return Response(serializer.data)
