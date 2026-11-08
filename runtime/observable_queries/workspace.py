"""Callback subscriptions to explicit workspace-scoped observable queries."""
from __future__ import annotations

from django.db.models import Q

from runtime.observable_queries.base import (
    Callback,
    _model_key,
    _model_name,
    _subscribe_queryset,
)
from runtime.observable_queries.root import ObservableRoot
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
        self._root = ObservableRoot()

    def get_cron_jobs(self, callback: Callback) -> ObservableSubscription:
        """Observe cron jobs assigned to this workspace."""
        return self._related("cron_jobs", callback)

    def get_session_versions(self, callback: Callback) -> ObservableSubscription:
        """Observe session versions assigned to this workspace."""
        return self._related("related_session_versions", callback)

    def get_terminals(self, callback: Callback) -> ObservableSubscription:
        """Observe terminals assigned to this workspace."""
        return self._related("terminals", callback)

    def get_agents(self, callback: Callback) -> ObservableSubscription:
        """Observe active global and project agents visible in this scope."""
        project_id = getattr(self.workspace, "parent_project_id")
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
        return self._observe_project_scope(AgentModel, queryset, callback)

    def get_skills(self, callback: Callback) -> ObservableSubscription:
        """Observe active global and project skills visible in this scope."""
        project_id = getattr(self.workspace, "parent_project_id")
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
        return self._observe_project_scope(SkillModel, queryset, callback)

    def _related(
        self,
        relation_name: str,
        callback: Callback,
    ) -> ObservableSubscription:
        queryset = getattr(self.workspace, relation_name).all()
        return self._root._observe_related(
            self.workspace,
            relation_name,
            queryset.model,
            callback,
            queryset=queryset,
        )

    def _observe_project_scope(self, model, queryset, callback):
        return _subscribe_queryset(
            queryset,
            model,
            (_model_key(model),),
            callback,
            lambda item: (
                item["model"] == _model_name(model)
                and not item.get("is_archived", False)
                and item.get("parent_agent_id") is None
                and item.get("parent_skill_id") is None
                and (
                    item.get("parent_project_id") is None
                    or item.get("parent_project_id")
                    == getattr(self.workspace, "parent_project_id")
                )
            ),
        )
