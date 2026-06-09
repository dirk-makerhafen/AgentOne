from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from server.models.collections.data_collection import DataCollection
from server.models.collections.collection_item import CollectionItem
from api.serializers.collections import (
    DataCollectionListSerializer, DataCollectionDetailSerializer,
    DataCollectionWriteSerializer, CollectionItemSerializer,
)


class CollectionViewSet(viewsets.ModelViewSet):
    queryset = DataCollection.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]
    ordering = ['-created_at']
    filterset_fields = ['name', 'collection_type', 'is_active']
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return DataCollectionListSerializer
        if self.action in ('create', 'partial_update', 'update'):
            return DataCollectionWriteSerializer
        return DataCollectionDetailSerializer

    @action(detail=True)
    def items(self, request, pk=None):
        collection = self.get_object()
        qs = collection.items.all().order_by('-created_at')
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = CollectionItemSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = CollectionItemSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        collection = self.get_object()
        from server.tasks.tick_scheduler import _propagate_from_collections
        try:
            _propagate_from_collections(collection)
            return Response({'status': 'reprocess triggered'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_ERROR)
