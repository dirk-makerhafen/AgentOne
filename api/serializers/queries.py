from rest_framework import serializers
from server.models.queries.query import Query
from server.models.queries.query_message import QueryMessage
from server.models.queries.response import Response


class QueryMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryMessage
        fields = ['id', 'role', 'content_prefix', 'content_postfix',
                  'tokens', 'created_at']


class ResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Response
        fields = ['id', 'status', 'content', 'reasoning', 'finish_reason',
                  'prompt_tokens', 'completion_tokens', 'tool_calls',
                  'total_time', 'created_at']


class QueryListSerializer(serializers.ModelSerializer):
    session_name = serializers.SerializerMethodField()
    response_status = serializers.SerializerMethodField()

    class Meta:
        model = Query
        fields = ['id', 'session_name', 'status', 'response_status',
                  'tokens', 'created_at', 'updated_at']

    def get_session_name(self, obj) -> str | None:
        return obj.session_version.session.name if obj.session_version else None

    def get_response_status(self, obj) -> str | None:
        try:
            return obj.related_response.status if obj.related_response else None
        except Exception:
            return None


class QueryDetailSerializer(serializers.ModelSerializer):
    messages = QueryMessageSerializer(many=True, read_only=True, source='related_query_messages')
    response = ResponseSerializer(read_only=True, source='related_response')

    class Meta:
        model = Query
        fields = ['id', 'session_version', 'status', 'messages', 'response',
                  'tokens', 'created_at', 'updated_at']


class QueryMessageWriteSerializer(serializers.Serializer):
    role = serializers.CharField(required=True)
    content = serializers.CharField(required=True)
