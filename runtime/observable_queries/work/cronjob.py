"""Observable Cronjob queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    pk_key,
    relation_key,
)


def _bool(value: bool) -> str:
    return str(value).lower()


class CronjobObservables(ObservableBase):
    @staticmethod
    def _model():
        from server.models.cron import Cronjob

        return Cronjob

    def root(self, *, archived: bool = False) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(is_archived=archived).order_by("-is_active", "name"),
            "Cronjob",
        )

    def by_project(self, project_id: int, *, archived: bool = False) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(parent_project_id=project_id, is_archived=archived)
            .order_by("-is_active", "name"),
            f"{relation_key(model, 'parent_project', project_id)}"
            f"@is_archived:{_bool(archived)}",
        )

    def by_agent(self, agent_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(agent_id=agent_id).order_by("-is_active", "name"),
            relation_key(model, "agent", agent_id),
        )

    def by_workspace(self, workspace_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(workspace_id=workspace_id).order_by("-is_active", "name"),
            relation_key(model, "workspace", workspace_id),
        )

    def by_pk(self, pk: int) -> ObservableList:
        model = self._model()
        return self._list(model.objects.filter(pk=pk), pk_key(model, pk))