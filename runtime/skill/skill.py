from __future__ import annotations
from pathlib import Path
from typing import Any

from server.models.skills.skill import SkillModel
from server.models.skills.skill_version import SkillModelVersion


class Skill:
    """Runtime wrapper around a SkillModel, delegating most reads to the
    pinned (or latest) SkillModelVersion."""

    def __init__(
        self,
        skill_model: SkillModel,
        pinned_skill_version: SkillModelVersion | None = None,
    ) -> None:
        self.model = skill_model
        self._pinned_skill_version = pinned_skill_version

    @property
    def name(self) -> str:
        """Return the skill's name."""
        return self.model.name

    @property
    def description(self) -> str:
        """Return the description from the active version."""
        return self.get_version_model().description

    @property
    def commit(self) -> str:
        """Return the commit hash from the active version."""
        return self.get_version_model().commit

    @property
    def path(self) -> str:
        """Return the filesystem path from the active version."""
        return self.get_version_model().path

    @property
    def version_number(self) -> int:
        """Return the version number of the active version."""
        return self.get_version_model().version_number

    @property
    def created_at(self) -> Any:
        """Return the creation timestamp of the active version."""
        return self.get_version_model().created_at

    def get_version_model(self) -> SkillModelVersion:
        """Return the pinned or latest SkillModelVersion."""
        if self._pinned_skill_version:
            return self._pinned_skill_version
        return self.model.latest_skill_version

    def all_versions(self) -> None:
        """Placeholder — not yet implemented."""
        pass

    # ------------------------------------------------------------------
    # Assistant wiring + navigation
    # ------------------------------------------------------------------

    #: Singular internal assistant working on ONE skill.
    ASSISTANT = "skill_assistant"

    @property
    def pk(self) -> Any:
        """Return the skill primary key."""
        return self.model.pk

    @property
    def project(self) -> Any:
        """Return the owning project, or *None* (global skill)."""
        try:
            return self.model.parent_project
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def get_source_dir(self) -> Path:
        """Return the skill's source directory (stored, else conventional)."""
        from runtime.paths import model_manifest_dir

        return model_manifest_dir(self.model, "skill", self.name, self.project)

    def get_skills_runtime(self) -> Any:
        """Return this skill's child skills."""
        from runtime.skill.skills import Skills

        return Skills(parent_skill=self.model)

    def get_agents_runtime(self) -> Any:
        """Return the agents owned by this skill."""
        from runtime.agents.agents import Agents

        return Agents(parent_skill=self.model)

    def get_assistant_workspace(self) -> Any:
        """Return the workspace row binding this skill's assistant sessions.

        The skill's source directory (stored ``manifest_dir`` first). Shared
        by ``get_assistant_session`` and UI panels so both bind the same row.
        """
        from runtime.workspace.workspaces import Workspaces

        source = self.get_source_dir()
        return Workspaces.ensure_named(
            f"{source.as_posix()} assistant scope",
            source,
            f"source scope for skill {self.name}",
        )

    def get_assistant_session(self, caller: Any = None, name: str | None = None) -> Any | None:
        """Return the singleton ``skill_assistant`` session in this scope."""
        from runtime.session.sessions import Sessions

        return Sessions().assistant_session(
            name or self.ASSISTANT,
            project=self.project,
            workspace=self.get_assistant_workspace(),
            caller=caller,
        )
