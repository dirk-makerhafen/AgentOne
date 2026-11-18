"""Observable DataCollection queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    relation_key,
)


class CollectionObservables(ObservableBase):
    @staticmethod
    def _model():
        from server.models.collections.data_collection import DataCollection

        return DataCollection

    def root(self) -> ObservableList:
        model = self._model()
        return self._list(model.objects.order_by("name"), "DataCollection")

    def by_project(self, project_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(parent_project_id=project_id).order_by("name"),
            relation_key(model, "parent_project", project_id),
        )