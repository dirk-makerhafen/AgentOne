from rest_framework import serializers
from server.models.project import Project


class ProjectListSerializer(serializers.ModelSerializer):
    path = serializers.CharField(source="main_workspace.path", read_only=True, default="")

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'path', 'created_at', 'updated_at']


class ProjectDetailSerializer(serializers.ModelSerializer):
    path = serializers.CharField(source="main_workspace.path", read_only=True, default="")
    main_workspace_path = serializers.CharField(
        source="main_workspace.path", read_only=True, default=""
    )
    agentone_dir = serializers.CharField(read_only=True)
    agent_count = serializers.SerializerMethodField()
    session_count = serializers.SerializerMethodField()
    cron_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'path', 'main_workspace_path',
                   'agentone_dir',
                  'agent_count', 'session_count', 'cron_count',
                  'created_at', 'updated_at']

    def get_agent_count(self, obj) -> int:
        return obj.child_agents.count()

    def get_session_count(self, obj) -> int:
        return obj.sessions.count()

    def get_cron_count(self, obj) -> int:
        return obj.child_crons.count()


class ProjectWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['name', 'description']
