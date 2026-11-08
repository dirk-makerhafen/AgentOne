"""Callback subscriptions to explicit root-level observable collections."""
from __future__ import annotations

from runtime.observable_queries.base import (
    Callback,
    _subscribe_queryset,
)
from runtime.observable_queries.subscription import ObservableSubscription


class ObservableRoot:
    """Named subscriptions for explicitly supported root collections."""

    def get_projects(self, callback: Callback) -> ObservableSubscription:
        """Observe the unordered set of projects."""
        from server.models.project import Project

        return _subscribe_queryset(
            Project.objects.all(),
            Project,
            ("Project",),
            callback,
            lambda item: item["model"] == "Project",
        )

    def get_agents(self, callback: Callback) -> ObservableSubscription:
        """Observe active, unparented global agents."""
        from server.models.agents.agent import AgentModel

        queryset = AgentModel.objects.filter(
            parent_project__isnull=True,
            parent_agent__isnull=True,
            parent_skill__isnull=True,
            is_archived=False,
        )
        return _subscribe_queryset(
            queryset,
            AgentModel,
            ("AgentModel",),
            callback,
            lambda item: (
                item["model"] == "AgentModel"
                and item.get("parent_project_id") is None
                and item.get("parent_agent_id") is None
                and item.get("parent_skill_id") is None
                and item.get("is_archived") is False
            ),
        )

    def get_skills(self, callback: Callback) -> ObservableSubscription:
        """Observe active, unparented global skills."""
        from server.models.skills.skill import SkillModel

        queryset = SkillModel.objects.filter(
            parent_project__isnull=True,
            parent_agent__isnull=True,
            parent_skill__isnull=True,
            is_archived=False,
        )
        return _subscribe_queryset(
            queryset,
            SkillModel,
            ("SkillModel",),
            callback,
            lambda item: (
                item["model"] == "SkillModel"
                and item.get("parent_project_id") is None
                and item.get("parent_agent_id") is None
                and item.get("parent_skill_id") is None
                and item.get("is_archived") is False
            ),
        )
