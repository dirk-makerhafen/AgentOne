from rest_framework import serializers
from server.models.skills.skill import SkillModel
from server.models.skills.skill_version import SkillModelVersion


class SkillVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SkillModelVersion
        fields = ['id', 'version_number', 'description', 'commit', 'path', 'created_at']


class SkillListSerializer(serializers.ModelSerializer):
    latest_version = serializers.SerializerMethodField()
    parent_agent_name = serializers.SerializerMethodField()
    parent_project_name = serializers.SerializerMethodField()

    class Meta:
        model = SkillModel
        fields = ['id', 'name', 'latest_version', 'parent_agent_name',
                  'parent_project_name', 'created_at', 'updated_at']

    def get_latest_version(self, obj) -> int | None:
        lv = obj.latest_skill_version
        return lv.version_number if lv else None

    def get_parent_agent_name(self, obj) -> str | None:
        return obj.parent_agent.name if obj.parent_agent else None

    def get_parent_project_name(self, obj) -> str | None:
        return obj.parent_project.name if obj.parent_project else None


class SkillDetailSerializer(serializers.ModelSerializer):
    versions = SkillVersionSerializer(many=True, read_only=True)
    parent_agent = serializers.SerializerMethodField()
    parent_project = serializers.SerializerMethodField()

    class Meta:
        model = SkillModel
        fields = ['id', 'name', 'versions', 'parent_agent',
                  'parent_project', 'created_at', 'updated_at']

    def get_parent_agent(self, obj) -> dict | None:
        return {'id': obj.parent_agent_id, 'name': obj.parent_agent.name} if obj.parent_agent else None

    def get_parent_project(self, obj) -> dict | None:
        return {'id': obj.parent_project_id, 'name': obj.parent_project.name} if obj.parent_project else None
