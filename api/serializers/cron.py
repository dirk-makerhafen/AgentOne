from rest_framework import serializers
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

    class Meta:
        model = Cronjob
        fields = ['id', 'name', 'description', 'schedule', 'is_active',
                  'agent', 'workspace', 'project',
                  'session_mode', 'session_name',
                  'function_type', 'function_name',
                  'last_run_at', 'next_run_at', 'last_status', 'total_runs',
                  'created_at', 'updated_at']

    def get_agent(self, obj) -> dict | None:
        return {'id': obj.agent_id, 'name': obj.agent.name} if obj.agent else None

    def get_workspace(self, obj) -> dict | None:
        return {'id': obj.workspace_id, 'name': obj.workspace.name} if obj.workspace else None

    def get_project(self, obj) -> dict | None:
        return {'id': obj.parent_project_id, 'name': obj.parent_project.name} if obj.parent_project else None


class CronWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cronjob
        fields = ['name', 'description', 'schedule', 'is_active',
                  'agent', 'workspace', 'parent_project',
                  'session_mode', 'session_name',
                  'function_type', 'function_name']
