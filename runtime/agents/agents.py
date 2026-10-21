from __future__ import annotations

from pathlib import Path
from typing import Any

from django.db.models import QuerySet, Q

from runtime.agents.agent import Agent
from runtime.assistant_scope import AssistantScopeMixin
from server.models.agents.agent import AgentModel


class Agents(AssistantScopeMixin):
    """Query interface for AgentModel instances.

    Scoping is explicit: ``parent_project`` selects the global agents plus
    that project's own (union); ``parent_agent``/``parent_skill`` select
    children; ``parent_workspace`` unwraps to its project; all *None*
    selects global agents only.
    """

    #: Collection domain label (used for the global system workspace name).
    DOMAIN = "agents"
    #: Internal assistant pair managing agents (singular, plural).
    ASSISTANT_NAMES = ("agent_assistant", "agents_assistant")

    def __init__(
        self,
        parent_agent: Any = None,
        parent_project: Any = None,
        parent_skill: Any = None,
        parent_workspace: Any = None,
    ) -> None:
        self.parent_agent = parent_agent
        self.parent_project = parent_project
        self.parent_skill = parent_skill
        self.parent_workspace = parent_workspace

    def all(self) -> QuerySet[AgentModel]:
        """Return active agents in scope, ordered by name (union for projects)."""
        qs = AgentModel.objects.filter(is_archived=False)
        if self.parent_agent is not None:
            qs = qs.filter(parent_agent=self.parent_agent)
        elif self.parent_skill is not None:
            qs = qs.filter(parent_skill=self.parent_skill)
        else:
            project = self.project
            if project is not None:
                qs = qs.filter(Q(parent_project=project) | Q(parent_project__isnull=True))
            else:
                qs = qs.filter(parent_project__isnull=True)
        return qs.select_related(
            "latest_agent_version", "parent_project", "parent_agent"
        ).order_by("name")

    def root(self) -> QuerySet[AgentModel]:
        """Return active top-level agents (those without a parent)."""
        return AgentModel.objects.filter(
            parent_skill=None,
            parent_agent=None,
            parent_project=None,
            is_archived=False,
        )

    def list_agents(self) -> list[Agent]:
        """Return agents in scope as wrapped :class:`Agent` objects."""
        return [Agent(agent_model=model) for model in self.all()]

    def wrap(self, agent_model: AgentModel) -> Agent:
        """Return the runtime :class:`Agent` wrapper for *agent_model*."""
        return agent_model.get_runtime()

    @staticmethod
    def global_home() -> Path:
        """Return the global agents directory (``~/.agentone/agents``)."""
        from runtime.paths import user_agents_dir

        path = user_agents_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # Assistant wiring
    # ------------------------------------------------------------------

    def get_source_dir(self) -> Path:
        """Return the source directory anchoring this scope (no I/O).

        Most-specific parent first: agent/skill source dir, project
        manifest, workspace manifest (or path), else the global home.
        """
        from runtime.paths import model_manifest_dir

        if self.parent_agent is not None:
            return model_manifest_dir(
                self.parent_agent, "agent",
                getattr(self.parent_agent, "name", ""),
                self.project,
            )
        if self.parent_skill is not None:
            return model_manifest_dir(
                self.parent_skill, "skill",
                getattr(self.parent_skill, "name", ""),
                self.project,
            )
        if self.parent_project is not None:
            return self.parent_project.get_agentone_dir()
        if self.parent_workspace is not None:
            return self.parent_workspace.get_agentone_dir()
        return self.global_home()

    def get_assistant_workspace(self) -> Any:
        """Return the workspace row binding this scope's assistant sessions.

        Nested scope: per-directory row; project scope: project workspace;
        global: system row. Shared by ``get_assistant_session`` and UI
        panels so both bind the same row.
        """
        from runtime.workspace.workspaces import Workspaces

        source = self.get_source_dir()
        project = self.project
        nested = self.parent_agent is not None or self.parent_skill is not None
        if nested:
            return Workspaces.ensure_named(
                f"{source.as_posix()} assistant scope", source,
                "assistant scope for nested agents",
            )
        if project is not None:
            return Workspaces.for_project(project)
        return Workspaces.ensure_named(
            "System agents", source, "User-scope agents manifests"
        )
