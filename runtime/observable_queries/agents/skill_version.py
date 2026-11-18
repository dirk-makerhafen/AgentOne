"""Observable SkillModelVersion queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    relation_key,
)


class SkillVersionObservables(ObservableBase):
    def by_skill(self, skill_id: int) -> ObservableList:
        from server.models.skills.skill_version import SkillModelVersion

        return self._list(
            SkillModelVersion.objects.filter(skill_id=skill_id).order_by("-created_at"),
            relation_key(SkillModelVersion, "skill", skill_id),
        )