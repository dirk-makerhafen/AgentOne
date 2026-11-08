"""Callback subscriptions to explicit workspace-scoped observable queries."""
from __future__ import annotations

from django.db.models import Q

from runtime.observable_queries.base import Callback, _subscribe_queryset
from runtime.observable_queries.subscription import ObservableSubscription
from server.models.agents.agent import AgentModel
from server.models.skills.skill import SkillModel
from server.models.workspace import WorkspaceModel


class ObservableWorkspace:
    """Observable collections associated with a workspace."""

    def __init__(self, workspace: WorkspaceModel):
        if not isinstance(workspace, WorkspaceModel):
            raise TypeError("ObservableWorkspace requires a WorkspaceModel")
        self.workspace = workspace

    def get_cron_jobs(self, callback: Callback) -> ObservableSubscription:
        """Observe cron jobs assigned to this workspace."""
        relation = self.workspace._meta.get_field("cron_jobs")
        queryset = self.workspace.cron_jobs.all()
        model = queryset.model
        foreign_key = relation.field
        return _subscribe_queryset(
            queryset,
            model,
            (model.__name__, f"{model.__name__}.{foreign_key.name}:{self.workspace.pk}"),
            callback,
            lambda item: (
                item["model"] == model.__name__
                and item.get(foreign_key.attname) == self.workspace.pk
            ),
        )

    def get_session_versions(self, callback: Callback) -> ObservableSubscription:
        """Observe session versions assigned to this workspace."""
        relation = self.workspace._meta.get_field("related_session_versions")
        queryset = self.workspace.related_session_versions.all()
        model = queryset.model
        foreign_key = relation.field
        return _subscribe_queryset(
            queryset,
            model,
            (model.__name__, f"{model.__name__}.{foreign_key.name}:{self.workspace.pk}"),
            callback,
            lambda item: (
                item["model"] == model.__name__
                and item.get(foreign_key.attname) == self.workspace.pk
            ),
        )

    def get_terminals(self, callback: Callback) -> ObservableSubscription:
        """Observe terminals assigned to this workspace."""
        relation = self.workspace._meta.get_field("terminals")
        queryset = self.workspace.terminals.all()
        model = queryset.model
        foreign_key = relation.field
        return _subscribe_queryset(
            queryset,
            model,
            (model.__name__, f"{model.__name__}.{foreign_key.name}:{self.workspace.pk}"),
            callback,
            lambda item: (
                item["model"] == model.__name__
                and item.get(foreign_key.attname) == self.workspace.pk
            ),
        )

    def get_agents(self, callback: Callback) -> ObservableSubscription:
        """Observe active global and project agents visible in this scope."""
        project_id = self.workspace.parent_project_id
        queryset = AgentModel.objects.filter(
            is_archived=False,
            parent_agent__isnull=True,
            parent_skill__isnull=True,
        )
        if project_id is None:
            queryset = queryset.filter(parent_project__isnull=True)
        else:
            queryset = queryset.filter(
                Q(parent_project_id=project_id) | Q(parent_project__isnull=True)
            )
        return _subscribe_queryset(
            queryset,
            AgentModel,
            ("AgentModel",),
            callback,
            lambda item: (
                item["model"] == "AgentModel"
                and item.get("is_archived") is False
                and item.get("parent_agent_id") is None
                and item.get("parent_skill_id") is None
                and (
                    item.get("parent_project_id") is None
                    or item.get("parent_project_id") == project_id
                )
            ),
        )

    def get_skills(self, callback: Callback) -> ObservableSubscription:
        """Observe active global and project skills visible in this scope."""
        project_id = self.workspace.parent_project_id
        queryset = SkillModel.objects.filter(
            is_archived=False,
            parent_agent__isnull=True,
            parent_skill__isnull=True,
        )
        if project_id is None:
            queryset = queryset.filter(parent_project__isnull=True)
        else:
            queryset = queryset.filter(
                Q(parent_project_id=project_id) | Q(parent_project__isnull=True)
            )
        return _subscribe_queryset(
            queryset,
            SkillModel,
            ("SkillModel",),
            callback,
            lambda item: (
                item["model"] == "SkillModel"
                and item.get("is_archived") is False
                and item.get("parent_agent_id") is None
                and item.get("parent_skill_id") is None
                and (
                    item.get("parent_project_id") is None
                    or item.get("parent_project_id") == project_id
                )
            ),
        )
