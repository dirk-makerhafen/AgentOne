from rest_framework import serializers
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.message import Message, MessagePart
from api.serializers.agents import _safe_runtime_settings


class SessionListSerializer(serializers.ModelSerializer):
    agent_name = serializers.SerializerMethodField()
    version_number = serializers.SerializerMethodField()

    class Meta:
        model = SessionModel
        fields = ['id', 'name', 'agent_name', 'version_number', 'is_active',
                  'is_archived', 'turn_count', 'created_at', 'updated_at']

    def get_agent_name(self, obj) -> str | None:
        sv = obj.latest_session_version
        return sv.agent.name if sv else None

    def get_version_number(self, obj) -> int | None:
        sv = obj.latest_session_version
        return sv.version_number if sv else None


class SessionDetailSerializer(serializers.ModelSerializer):
    agent = serializers.SerializerMethodField()
    settings = serializers.SerializerMethodField()
    workspace = serializers.SerializerMethodField()

    class Meta:
        model = SessionModel
        fields = ['id', 'name', 'agent', 'settings', 'workspace',
                  'is_active', 'is_archived', 'is_pinned',
                  'turn_count', 'unattended_turn_count',
                  'parent_project', 'created_at', 'updated_at']

    def get_agent(self, obj) -> dict | None:
        sv = obj.latest_session_version
        if not sv:
            return None
        return {'id': sv.agent_id, 'name': sv.agent.name}

    def get_settings(self, obj) -> dict:
        return _safe_runtime_settings(obj)

    def get_workspace(self, obj) -> dict | None:
        sv = obj.latest_session_version
        if not sv or not sv.workspace:
            return None
        return {'id': sv.workspace_id, 'name': sv.workspace.name}


class SessionWriteSerializer(serializers.Serializer):
    agent_id = serializers.IntegerField(required=True)
    name = serializers.CharField(required=False, allow_blank=True)
    aimodel = serializers.IntegerField(required=False, allow_null=True)
    reasoning_effort = serializers.CharField(required=False, allow_null=True)
    scheduler_strategy = serializers.CharField(required=False, allow_null=True)
    tool_call_syntax = serializers.CharField(required=False, allow_null=True)
    subagentResultDelivery = serializers.CharField(required=False, allow_null=True)
    max_retries = serializers.IntegerField(required=False, allow_null=True)
    max_turns = serializers.IntegerField(required=False, allow_null=True)
    max_unattended_turns = serializers.IntegerField(required=False, allow_null=True)
    precision = serializers.FloatField(required=False, allow_null=True)
    max_history_messages = serializers.IntegerField(required=False, allow_null=True)
    priority = serializers.IntegerField(required=False, allow_null=True)


class MessagePartSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessagePart
        fields = ['id', 'type', 'content_type', 'tokens']


class MessageSerializer(serializers.ModelSerializer):
    parts = MessagePartSerializer(many=True, read_only=True)
    role_display = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'role', 'role_display', 'source', 'parts',
                  'hide_from_context', 'created_at']

    def get_role_display(self, obj):
        return obj.get_role_display() if hasattr(obj, 'get_role_display') else obj.role


class SessionVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionVersionModel
        fields = ['id', 'version_number', 'created_at']
