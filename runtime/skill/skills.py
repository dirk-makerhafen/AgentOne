from __future__ import annotations

from pathlib import Path
from typing import Any

from django.db.models import QuerySet, Q

from runtime.assistant_scope import AssistantScopeMixin
from server.models.skills.skill import SkillModel


class Skills(AssistantScopeMixin):
    """Query interface for SkillModel instances.

    Scoping is explicit: ``parent_project`` selects the global skills plus
    that project's own (union); ``parent_agent``/``parent_skill`` select
    children; ``parent_workspace`` unwraps to its project; all *None*
    selects global skills only.
    """

    #: Collection domain label (used for the global system workspace name).
    DOMAIN = "skills"
    #: Internal assistant pair managing skills (singular, plural).
    ASSISTANT_NAMES = ("skill_assistant", "skills_assistant")

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

    def all(self) -> QuerySet[SkillModel]:
        """Return active skills in scope, ordered by name (union for projects)."""
        qs = SkillModel.objects.filter(is_archived=False)
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
        return qs.select_related("latest_skill_version", "parent_project").order_by("name")

    def root(self) -> QuerySet[SkillModel]:
        """Return all active skills (unscoped; UI + legacy callers)."""
        return SkillModel.objects.filter(is_archived=False)

    def list_skills(self) -> list:
        """Return skills in scope as wrapped :class:`Skill` objects."""
        from runtime.skill.skill import Skill

        return [Skill(model) for model in self.all()]

    @staticmethod
    def global_home() -> Path:
        """Return the global skills directory (``~/.agentone/skills``)."""
        from runtime.paths import user_skills_dir

        path = user_skills_dir()
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
                "assistant scope for nested skills",
            )
        if project is not None:
            return Workspaces.for_project(project)
        return Workspaces.ensure_named(
            "System skills", source, "User-scope skills manifests"
        )
