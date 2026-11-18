"""Observable Project queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    pk_key,
    root_key,
)


class ProjectObservables(ObservableBase):
    @staticmethod
    def _model():
        from server.models.project import Project

        return Project

    def root(self) -> ObservableList:
        model = self._model()
        return self._list(model.objects.order_by("name"), root_key(model))

    def by_pk(self, pk: int) -> ObservableList:
        model = self._model()
        return self._list(model.objects.filter(pk=pk), pk_key(model, pk))