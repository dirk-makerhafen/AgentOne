from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from server.models.cron import Cronjob
from api.serializers.cron import (
    CronListSerializer, CronDetailSerializer, CronWriteSerializer,
)
from runtime.cron.execute import execute_cron_job


class CronViewSet(viewsets.ModelViewSet):
    queryset = Cronjob.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    filterset_fields = ['name', 'is_active', 'schedule']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return CronListSerializer
        if self.action in ('create', 'partial_update', 'update'):
            return CronWriteSerializer
        return CronDetailSerializer

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        cronjob = self.get_object()
        try:
            execute_cron_job(cronjob.id)
            return Response({'status': 'triggered'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_ERROR)
