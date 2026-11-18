"""Observable SkillModel queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    pk_key,
    relation_key,
)


def _archived(value: bool) -> str:
    return str(value).lower()


class SkillObservables(ObservableBase):
    @staticmethod
    def _model():
        from server.models.skills.skill import SkillModel

        return SkillModel

    def root(self, *, archived: bool = False) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(is_archived=archived).order_by("name"),
            "SkillModel",
        )

    def by_parent_project(self, project_id: int, *, archived: bool = False) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(parent_project_id=project_id, is_archived=archived)
            .select_related("parent_project")
            .order_by("name"),
            f"{relation_key(model, 'parent_project', project_id)}"
            f"@is_archived:{_archived(archived)}",
        )

    def by_parent_agent(self, parent_agent_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(parent_agent_id=parent_agent_id).order_by("name"),
            relation_key(model, "parent_agent", parent_agent_id),
        )

    def by_parent_skill(self, parent_skill_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(parent_skill_id=parent_skill_id).order_by("name"),
            relation_key(model, "parent_skill", parent_skill_id),
        )

    def by_pk(self, pk: int) -> ObservableList:
        model = self._model()
        return self._list(model.objects.filter(pk=pk), pk_key(model, pk))