"""Callback subscriptions to explicit project-scoped observable queries."""
from __future__ import annotations

from runtime.observable_queries.base import Callback, _subscribe_queryset
from runtime.observable_queries.subscription import ObservableSubscription
from server.models.project import Project


class ObservableProject:
    """Observable collections owned by one project."""

    def __init__(self, project: Project):
        if not isinstance(project, Project):
            raise TypeError("ObservableProject requires a Project")
        self.project = project

    def get_agents(self, callback: Callback) -> ObservableSubscription:
        """Observe active agents owned by this project."""
        from server.models.agents.agent import AgentModel

        queryset = AgentModel.objects.filter(
            parent_project=self.project,
            is_archived=False,
        )
        return _subscribe_queryset(
            queryset,
            AgentModel,
            ("AgentModel", f"AgentModel.parent_project:{self.project.pk}"),
            callback,
            lambda item: (
                item["model"] == "AgentModel"
                and item.get("parent_project_id") == self.project.pk
                and item.get("is_archived") is False
            ),
        )

    def get_skills(self, callback: Callback) -> ObservableSubscription:
        """Observe active skills owned by this project."""
        from server.models.skills.skill import SkillModel

        queryset = SkillModel.objects.filter(
            parent_project=self.project,
            is_archived=False,
        )
        return _subscribe_queryset(
            queryset,
            SkillModel,
            ("SkillModel", f"SkillModel.parent_project:{self.project.pk}"),
            callback,
            lambda item: (
                item["model"] == "SkillModel"
                and item.get("parent_project_id") == self.project.pk
                and item.get("is_archived") is False
            ),
        )

    def get_sessions(self, callback: Callback) -> ObservableSubscription:
        """Observe sessions directly owned by this project."""
        from server.models.sessions.session import SessionModel

        queryset = SessionModel.objects.filter(parent_project=self.project)
        return _subscribe_queryset(
            queryset,
            SessionModel,
            ("SessionModel", f"SessionModel.parent_project:{self.project.pk}"),
            callback,
            lambda item: (
                item["model"] == "SessionModel"
                and item.get("parent_project_id") == self.project.pk
            ),
        )

    def get_workspaces(self, callback: Callback) -> ObservableSubscription:
        """Observe workspaces owned by this project."""
        from server.models.workspace import WorkspaceModel

        queryset = WorkspaceModel.objects.filter(parent_project=self.project)
        return _subscribe_queryset(
            queryset,
            WorkspaceModel,
            ("WorkspaceModel", f"WorkspaceModel.parent_project:{self.project.pk}"),
            callback,
            lambda item: (
                item["model"] == "WorkspaceModel"
                and item.get("parent_project_id") == self.project.pk
            ),
        )

    def get_cron_jobs(self, callback: Callback) -> ObservableSubscription:
        """Observe cron jobs owned by this project."""
        from server.models.cron import Cronjob

        queryset = Cronjob.objects.filter(parent_project=self.project)
        return _subscribe_queryset(
            queryset,
            Cronjob,
            ("Cronjob", f"Cronjob.parent_project:{self.project.pk}"),
            callback,
            lambda item: (
                item["model"] == "Cronjob"
                and item.get("parent_project_id") == self.project.pk
            ),
        )

    def get_task_definitions(self, callback: Callback) -> ObservableSubscription:
        """Observe task definitions owned by this project."""
        from server.models.tasks.task_definition import TaskDefinition

        queryset = TaskDefinition.objects.filter(parent_project=self.project)
        return _subscribe_queryset(
            queryset,
            TaskDefinition,
            (
                "TaskDefinition",
                f"TaskDefinition.parent_project:{self.project.pk}",
            ),
            callback,
            lambda item: (
                item["model"] == "TaskDefinition"
                and item.get("parent_project_id") == self.project.pk
            ),
        )

    def get_work_items(self, callback: Callback) -> ObservableSubscription:
        """Observe work items owned by this project."""
        from server.models.workitems.work_item import WorkItem

        queryset = WorkItem.objects.filter(project=self.project)
        return _subscribe_queryset(
            queryset,
            WorkItem,
            ("WorkItem", f"WorkItem.project:{self.project.pk}"),
            callback,
            lambda item: (
                item["model"] == "WorkItem"
                and item.get("project_id") == self.project.pk
            ),
        )

    def get_data_collections(self, callback: Callback) -> ObservableSubscription:
        """Observe data collections owned by this project."""
        from server.models.collections.data_collection import DataCollection

        queryset = DataCollection.objects.filter(parent_project=self.project)
        return _subscribe_queryset(
            queryset,
            DataCollection,
            (
                "DataCollection",
                f"DataCollection.parent_project:{self.project.pk}",
            ),
            callback,
            lambda item: (
                item["model"] == "DataCollection"
                and item.get("parent_project_id") == self.project.pk
            ),
        )
