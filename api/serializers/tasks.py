from rest_framework import serializers
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun


class TaskRunSerializer(serializers.ModelSerializer):
    task_name = serializers.SerializerMethodField()

    class Meta:
        model = AgentTaskRun
        fields = ['id', 'agent_task_call', 'task_name', 'status',
                  'arguments_json', 'result_json',
                  'priority', 'ended_at', 'created_at', 'updated_at']

    def get_task_name(self, obj) -> str | None:
        if not obj:
            return None
        tdv = obj.task_definition_version
        return tdv.task_definition.name if tdv and tdv.task_definition else None


class TaskCallListSerializer(serializers.ModelSerializer):
    task_name = serializers.SerializerMethodField()
    session_name = serializers.SerializerMethodField()

    class Meta:
        model = AgentTaskCall
        fields = ['id', 'task_name', 'session_name', 'session',
                  'status', 'status_detail', 'carguments_json',
                  'is_approved', 'retry_count', 'priority',
                  'ended_at', 'created_at', 'updated_at']

    def get_task_name(self, obj) -> str | None:
        if not obj:
            return None
        tdv = obj.task_definition_version
        return tdv.task_definition.name if tdv and tdv.task_definition else None

    def get_session_name(self, obj) -> str | None:
        return obj.session.name if obj.session else None


class TaskCallDetailSerializer(serializers.ModelSerializer):
    runs = TaskRunSerializer(many=True, read_only=True, source='related_agent_task_runs')
    task_name = serializers.SerializerMethodField()
    session_name = serializers.SerializerMethodField()

    class Meta:
        model = AgentTaskCall
        fields = ['id', 'task_name', 'session_name', 'session',
                  'task_definition', 'task_definition_version',
                  'task_instance', 'carguments_json',
                  'status', 'status_detail',
                  'requires_approval', 'is_approved',
                  'retry_count', 'max_retries', 'retry_delay',
                  'priority', 'time_limit',
                  'dont_start_before', 'dont_start_after',
                  'ended_at', 'runs', 'created_at', 'updated_at']

    def get_task_name(self, obj) -> str | None:
        if not obj:
            return None
        tdv = obj.task_definition_version
        return tdv.task_definition.name if tdv and tdv.task_definition else None

    def get_session_name(self, obj) -> str | None:
        return obj.session.name if obj.session else None
