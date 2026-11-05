from rest_framework import serializers

from runtime.cron.content import build_cron_message
from server.models.cron import Cronjob


class CronListSerializer(serializers.ModelSerializer):
    agent_name = serializers.SerializerMethodField()

    class Meta:
        model = Cronjob
        fields = ['id', 'name', 'schedule', 'is_active', 'agent_name',
                  'last_run_at', 'next_run_at', 'last_status', 'total_runs',
                  'created_at', 'updated_at']

    def get_agent_name(self, obj) -> str | None:
        return obj.agent.name if obj.agent else None


class CronDetailSerializer(serializers.ModelSerializer):
    agent = serializers.SerializerMethodField()
    workspace = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()

    class Meta:
        model = Cronjob
        fields = ['id', 'name', 'description', 'schedule', 'is_active',
                  'agent', 'workspace', 'project', 'message',
                  'session_mode', 'session_name',
                  'function_type', 'function_name',
                  'last_run_at', 'next_run_at', 'last_status', 'total_runs',
                  'created_at', 'updated_at']

    def get_message(self, obj):
        return obj.message.get() if obj.message else None

    def get_agent(self, obj) -> dict | None:
        return {'id': obj.agent_id, 'name': obj.agent.name} if obj.agent else None

    def get_workspace(self, obj) -> dict | None:
        return {'id': obj.workspace_id, 'name': obj.workspace.name} if obj.workspace else None

    def get_project(self, obj) -> dict | None:
        return {'id': obj.parent_project_id, 'name': obj.parent_project.name} if obj.parent_project else None


class CronWriteSerializer(serializers.ModelSerializer):
    # DRF's BooleanField treats a missing HTML/multipart value as ``False``.
    # Default to the model's "active" behaviour so a minimal create payload
    # does not silently produce a job that never runs.
    is_active = serializers.BooleanField(required=False, default=True)
    # Plain text/JSON args, converted through the same helper as the UI,
    # assistant tools and manifest loader.
    message = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = Cronjob
        fields = ['name', 'description', 'schedule', 'is_active',
                  'agent', 'workspace', 'parent_project',
                  'session_mode', 'session_name',
                  'function_type', 'function_name', 'message']

    def create(self, validated_data):
        message = validated_data.pop('message', '')
        function_type = validated_data.get('function_type', '')
        try:
            content = build_cron_message(message, function_type)
        except ValueError as exc:
            raise serializers.ValidationError({'message': str(exc)}) from exc
        return Cronjob.objects.create(message=content, **validated_data)

    def update(self, instance, validated_data):
        if 'message' in validated_data:
            message = validated_data.pop('message')
            function_type = validated_data.get('function_type', instance.function_type)
            try:
                instance.message = build_cron_message(message, function_type)
            except ValueError as exc:
                raise serializers.ValidationError({'message': str(exc)}) from exc
        return super().update(instance, validated_data)
