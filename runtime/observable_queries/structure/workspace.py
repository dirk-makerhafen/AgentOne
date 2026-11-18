"""Observable WorkspaceModel queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    relation_key,
)


class WorkspaceObservables(ObservableBase):
    @staticmethod
    def _model():
        from server.models.workspace import WorkspaceModel

        return WorkspaceModel

    def root(self) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(parent_project__isnull=True).order_by("name"),
            "WorkspaceModel",
        )

    def by_project(self, project_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(parent_project_id=project_id).order_by("name"),
            relation_key(model, "parent_project", project_id),
        )