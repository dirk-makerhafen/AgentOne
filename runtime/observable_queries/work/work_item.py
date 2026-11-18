"""Observable WorkItem queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    pk_key,
    relation_key,
)


def _bool(value: bool) -> str:
    return str(value).lower()


class WorkItemObservables(ObservableBase):
    @staticmethod
    def _model():
        from server.models.workitems.work_item import WorkItem

        return WorkItem

    def root(self, *, terminal: bool = False) -> ObservableList:
        model = self._model()
        queryset = model.objects.all()
        if not terminal:
            queryset = queryset.exclude(status__in=self._terminal())
        return self._list(
            queryset.order_by("-priority", "created_at"),
            "WorkItem",
        )

    def by_project(self, project_id: int, *, terminal: bool = False) -> ObservableList:
        model = self._model()
        queryset = model.objects.filter(project_id=project_id)
        if not terminal:
            queryset = queryset.exclude(status__in=self._terminal())
        return self._list(
            queryset.order_by("-priority", "created_at"),
            f"{relation_key(model, 'project', project_id)}@terminal:{_bool(terminal)}",
        )

    def by_pk(self, pk: int) -> ObservableList:
        model = self._model()
        return self._list(model.objects.filter(pk=pk), pk_key(model, pk))

    @staticmethod
    def _terminal():
        from server.models.workitems.enums import WorkItemStatus

        return (WorkItemStatus.DONE, WorkItemStatus.CANCELLED)