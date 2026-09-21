from rest_framework import serializers
from server.models.workspace import WorkspaceModel


class WorkspaceListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceModel
        fields = ['id', 'name', 'description', 'path', 'color', 'access', 'created_at', 'updated_at']


class WorkspaceDetailSerializer(serializers.ModelSerializer):
    session_count = serializers.SerializerMethodField()
    cron_count = serializers.SerializerMethodField()

    class Meta:
        model = WorkspaceModel
        fields = ['id', 'name', 'description', 'path', 'color', 'access',
                  'session_count', 'cron_count',
                  'created_at', 'updated_at']

    def get_session_count(self, obj) -> int:
        return obj.related_session_versions.count()

    def get_cron_count(self, obj) -> int:
        return obj.cron_jobs.count()


class WorkspaceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkspaceModel
        fields = ['name', 'description', 'path', 'color', 'access']
