from rest_framework import viewsets, serializers
from rest_framework.permissions import IsAuthenticated
from django_filters import rest_framework as filters

from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from api.serializers.tasks import (
    TaskCallListSerializer, TaskCallDetailSerializer, TaskRunSerializer,
)


class TaskCallFilter(filters.FilterSet):
    session = filters.NumberFilter(field_name='session_id')
    status = filters.CharFilter(field_name='status')
    task_name = filters.CharFilter(field_name='task_definition_version__task_definition__name')

    class Meta:
        model = AgentTaskCall
        fields = ['session', 'status', 'task_name']


class TaskCallViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AgentTaskCall.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    filterset_class = TaskCallFilter
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return TaskCallListSerializer
        return TaskCallDetailSerializer


class TaskRunFilter(filters.FilterSet):
    task_call = filters.NumberFilter(field_name='agent_task_call_id')
    status = filters.CharFilter(field_name='status')

    class Meta:
        model = AgentTaskRun
        fields = ['task_call', 'status']


class TaskRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AgentTaskRun.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    filterset_class = TaskRunFilter
    ordering = ['-created_at']
    serializer_class = TaskRunSerializer
