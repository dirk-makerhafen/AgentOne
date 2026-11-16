"""Observable cron / collection / work-item collections."""
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


class CollectionItemObservables(ObservableBase):
    def by_collection(self, collection_id: int) -> ObservableList:
        from server.models.collections.collection_item import CollectionItem

        return self._list(
            CollectionItem.objects.filter(collection_id=collection_id).order_by("created_at", "pk"),
            relation_key(CollectionItem, "collection", collection_id),
        )


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
