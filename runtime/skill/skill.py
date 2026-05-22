from __future__ import annotations
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
