from rest_framework import serializers
from server.models.system import System


class SystemListSerializer(serializers.ModelSerializer):
    class Meta:
        model = System
        fields = ['id', 'name', 'description', 'status', 'os',
                  'last_heartbeat', 'executor_mode', 'created_at', 'updated_at']


class SystemDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = System
        fields = ['id', 'name', 'description', 'status', 'os',
                  'last_heartbeat', 'executor_mode', 'executor_url',
                  'created_at', 'updated_at']
        read_only_fields = ['executor_api_key', 'name']


class SystemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = System
        fields = ['description', 'status', 'os', 'executor_mode', 'executor_url']
