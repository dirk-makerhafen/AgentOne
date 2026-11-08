"""Callback subscriptions to explicit project-scoped observable queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    Callback,
    _filtered_predicate,
    _model_key,
    _model_name,
    _subscribe_queryset,
)
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

        return self._children(
            AgentModel,
            "parent_project",
            callback,
            order_by=("name",),
            is_archived=False,
        )

    def get_skills(self, callback: Callback) -> ObservableSubscription:
        """Observe active skills owned by this project."""
        from server.models.skills.skill import SkillModel

        return self._children(
            SkillModel,
            "parent_project",
            callback,
            order_by=("name",),
            is_archived=False,
        )

    def get_sessions(self, callback: Callback) -> ObservableSubscription:
        """Observe sessions directly owned by this project."""
        from server.models.sessions.session import SessionModel

        return self._children(
            SessionModel, "parent_project", callback, order_by=("-created_at",)
        )

    def get_workspaces(self, callback: Callback) -> ObservableSubscription:
        from server.models.workspace import WorkspaceModel

        return self._children(
            WorkspaceModel, "parent_project", callback, order_by=("name",)
        )

    def get_cron_jobs(self, callback: Callback) -> ObservableSubscription:
        from server.models.cron import Cronjob

        return self._children(Cronjob, "parent_project", callback, order_by=("name",))

    def get_task_definitions(self, callback: Callback) -> ObservableSubscription:
        from server.models.tasks.task_definition import TaskDefinition

        return self._children(
            TaskDefinition, "parent_project", callback, order_by=("name",)
        )

    def get_work_items(self, callback: Callback) -> ObservableSubscription:
        from server.models.workitems.work_item import WorkItem

        return self._children(WorkItem, "project", callback, order_by=("-created_at",))

    def get_data_collections(self, callback: Callback) -> ObservableSubscription:
        from server.models.collections.data_collection import DataCollection

        return self._children(
            DataCollection, "parent_project", callback, order_by=("name",)
        )

    def _children(
        self,
        model,
        field_name: str,
        callback: Callback,
        order_by: tuple[str, ...] = (),
        **conditions,
    ):
        field = model._meta.get_field(field_name)
        queryset = model._default_manager.filter(
            **{field.name: self.project},
            **conditions,
        )
        if order_by:
            queryset = queryset.order_by(*order_by)
        relation_key = f"{_model_name(model)}.{field.name}:{self.project.pk}"
        expected = {
            field.attname: self.project.pk,
            **{name: value for name, value in conditions.items()},
        }
        predicate = _filtered_predicate(model, lambda item: True, **expected)
        return _subscribe_queryset(
            queryset,
            model,
            (_model_key(model), relation_key),
            callback,
            predicate,
        )
