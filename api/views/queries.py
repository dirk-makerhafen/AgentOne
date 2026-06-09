from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters import rest_framework as filters

from server.models.queries.query import Query
from api.serializers.queries import QueryListSerializer, QueryDetailSerializer


class QueryFilter(filters.FilterSet):
    session = filters.NumberFilter(field_name='session_version__session_id')
    status = filters.CharFilter(field_name='status')

    class Meta:
        model = Query
        fields = ['session', 'status']


class QueryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Query.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    filterset_class = QueryFilter
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return QueryListSerializer
        return QueryDetailSerializer

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        query = self.get_object()
        query.status = 'CANCELLED'
        query.save(update_fields=['status'])
        return Response({'status': 'cancelled'})
