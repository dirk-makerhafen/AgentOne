from __future__ import annotations

from pathlib import Path
from typing import Any

from django.db.models import QuerySet, Q

from server.models.skills.skill import SkillModel


class Skills:
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

    @property
    def project(self) -> Any | None:
        """Return the scope project (explicit, workspace/owner-unwrapped)."""
        if self.parent_project is not None:
            return self.parent_project
        for owner in (self.parent_workspace, self.parent_agent, self.parent_skill):
            try:
                project = getattr(owner, "parent_project", None)
                if project is not None:
                    return project
            except Exception:  # pylint: disable=broad-exception-caught
                continue
        return None

    def all(self) -> QuerySet[SkillModel]:
        """Return skills in scope, ordered by name (union for projects)."""
        qs = SkillModel.objects.all()
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
        """Return all skills (unscoped; UI + legacy callers)."""
        return SkillModel.objects.filter()

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

    @property
    def assistant_name(self) -> str:
        """Return the collection assistant managing this scope."""
        return self.ASSISTANT_NAMES[1]

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
            from runtime.paths import project_manifest_dir

            return project_manifest_dir(self.parent_project)
        if self.parent_workspace is not None:
            return model_manifest_dir(self.parent_workspace, "workspace")
        return self.global_home()

    def get_assistant_session(self, caller: Any = None, name: str | None = None) -> Any | None:
        """Return the singleton skills-assistant session for this scope.

        *name* defaults to the collection assistant; pass the singular
        name to talk about ONE skill (named inside the task text).
        """
        from runtime.session.sessions import Sessions
        from runtime.workspace.workspaces import Workspaces

        source = self.get_source_dir()
        project = self.project
        nested = self.parent_agent is not None or self.parent_skill is not None
        if nested:
            workspace = Workspaces.ensure_named(
                f"{source.as_posix()} assistant scope", source,
                "assistant scope for nested skills",
            )
        elif project is not None:
            workspace = Workspaces.for_project(project)
        else:
            workspace = Workspaces.ensure_named(
                "System skills", source, "User-scope skills manifests"
            )
        return Sessions().assistant_session(
            name or self.assistant_name,
            project=project,
            workspace=workspace,
            caller=caller,
        )
