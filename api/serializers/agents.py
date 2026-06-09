from rest_framework import serializers
from server.models.agents.agent import AgentModel
from server.models.agents.agent_version import AgentVersionModel
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from server.models.skills.skill_version import SkillModelVersion


class AgentListSerializer(serializers.ModelSerializer):
    version_number = serializers.SerializerMethodField()
    parent_agent_name = serializers.SerializerMethodField()
    parent_skill_name = serializers.SerializerMethodField()
    parent_project_name = serializers.SerializerMethodField()

    class Meta:
        model = AgentModel
        fields = [
            'id', 'name', 'version_number', 'created_at', 'updated_at',
            'parent_agent_name', 'parent_skill_name', 'parent_project_name',
        ]

    def get_version_number(self, obj) -> int | None:
        lv = obj.latest_agent_version
        return lv.version_number if lv else None

    def get_parent_agent_name(self, obj) -> str | None:
        return obj.parent_agent.name if obj.parent_agent else None

    def get_parent_skill_name(self, obj) -> str | None:
        return obj.parent_skill.name if obj.parent_skill else None

    def get_parent_project_name(self, obj) -> str | None:
        return obj.parent_project.name if obj.parent_project else None


def _safe_runtime_settings(agent_or_session):
    try:
        rt = agent_or_session.get_runtime()
    except Exception:
        return {}
    try:
        return {
            'aimodel': rt.aimodel,
            'reasoning_effort': rt.reasoning_effort,
            'max_retries': rt.max_retries,
            'max_turns': rt.max_turns,
            'max_unattended_turns': rt.max_unattended_turns,
            'precision': rt.precision,
            'max_history_messages': rt.max_history_messages,
            'priority': rt.priority,
            'scheduler_strategy': rt.scheduler_strategy,
            'tool_call_syntax': rt.tool_call_syntax,
            'subagentResultDelivery': rt.subagentResultDelivery,
        }
    except Exception:
        return {}


class AgentDetailSerializer(serializers.ModelSerializer):
    version_number = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    settings = serializers.SerializerMethodField()
    parent_agent = serializers.SerializerMethodField()
    parent_skill = serializers.SerializerMethodField()
    parent_project = serializers.SerializerMethodField()

    class Meta:
        model = AgentModel
        fields = [
            'id', 'name', 'version_number', 'description', 'settings',
            'parent_agent', 'parent_skill', 'parent_project',
            'created_at', 'updated_at',
        ]

    def get_version_number(self, obj) -> int | None:
        lv = obj.latest_agent_version
        return lv.version_number if lv else None

    def get_description(self, obj) -> str:
        lv = obj.latest_agent_version
        return lv.description if lv else ''

    def get_settings(self, obj) -> dict:
        return _safe_runtime_settings(obj)

    def get_parent_agent(self, obj) -> dict | None:
        return {'id': obj.parent_agent_id, 'name': obj.parent_agent.name} if obj.parent_agent else None

    def get_parent_skill(self, obj) -> dict | None:
        return {'id': obj.parent_skill_id, 'name': obj.parent_skill.name} if obj.parent_skill else None

    def get_parent_project(self, obj) -> dict | None:
        return {'id': obj.parent_project_id, 'name': obj.parent_project.name} if obj.parent_project else None


class AgentVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentVersionModel
        fields = ['id', 'version_number', 'description', 'commit', 'created_at']


class TaskDefinitionVersionSerializer(serializers.ModelSerializer):
    task_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskDefinitionVersion
        fields = ['id', 'task_name', 'description', 'task_type', 'function_name',
                  'requires_approval', 'bound', 'time_limit', 'priority']

    def get_task_name(self, obj):
        return obj.task_definition.name if obj.task_definition else ''


class SkillVersionRefSerializer(serializers.ModelSerializer):
    skill_name = serializers.SerializerMethodField()

    class Meta:
        model = SkillModelVersion
        fields = ['id', 'skill_name', 'description', 'version_number', 'path']

    def get_skill_name(self, obj):
        return obj.skill.name if obj.skill else ''


class AgentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentModel
        fields = ['name']
