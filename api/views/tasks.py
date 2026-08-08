from rest_framework import viewsets, serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
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

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a task call that is halted for approval."""
        from runtime.tasks.call_fsm import TaskCallStateMachine

        try:
            task_call = self.get_object()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        if task_call.status_detail != "HALTED_APPROVAL":
            return Response(
                {'error': f'Call is not awaiting approval (status: {task_call.status_detail})'},
                status=status.HTTP_409_CONFLICT,
            )

        if not TaskCallStateMachine.approve(task_call.pk):
            return Response(
                {'error': 'Could not approve call'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({'status': 'approved'})

    @action(detail=True, methods=['post'])
    def deny(self, request, pk=None):
        """Deny a task call that is halted for approval.

        Accepts an optional ``feedback`` body field: a comment from the user
        that is passed back to the LLM together with the denial.
        """
        from runtime.tasks.call_scheduler import CallScheduler
        from server.models.enums.task_enums import TaskCallStatusDetail

        try:
            task_call = self.get_object()
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        if task_call.status_detail != "HALTED_APPROVAL":
            return Response(
                {'error': f'Call is not awaiting approval (status: {task_call.status_detail})'},
                status=status.HTTP_409_CONFLICT,
            )

        feedback = ""
        if isinstance(request.data, dict):
            feedback = str(request.data.get("feedback", "") or "")

        try:
            denied = CallScheduler.deny_taskcall(task_call.pk, feedback=feedback)
        except Exception:
            denied = False

        if not denied:
            return Response(
                {'error': 'Could not deny call'},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({'status': 'denied'})


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
