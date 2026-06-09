from rest_framework import serializers
from server.models.collections.data_collection import DataCollection
from server.models.collections.collection_item import CollectionItem


class DataCollectionListSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = DataCollection
        fields = ['id', 'name', 'collection_type', 'description',
                  'is_active', 'item_count', 'created_at', 'updated_at']

    def get_item_count(self, obj) -> int:
        return obj.items.count()


class DataCollectionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataCollection
        fields = ['id', 'name', 'description', 'collection_type',
                  'is_active', 'sources', 'processor', 'on_removed',
                  'member_field', 'score_field',
                  'retroactive_on_source_change', 'max_reprocess',
                  'created_at', 'updated_at']


class DataCollectionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataCollection
        fields = ['name', 'description', 'collection_type', 'is_active',
                  'sources', 'processor', 'on_removed',
                  'member_field', 'score_field',
                  'retroactive_on_source_change', 'max_reprocess']


class CollectionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectionItem
        fields = ['id', 'collection', 'source_call', 'member', 'score',
                  'value', 'created_at']
