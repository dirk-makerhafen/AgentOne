"""Observable SessionModel queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    ObservableValue,
    pk_key,
    relation_key,
    root_key,
)


class SessionObservables(ObservableBase):
    model = None  # set lazily to keep model imports out of module import time

    @staticmethod
    def _model():
        from server.models.sessions.session import SessionModel

        return SessionModel

    def root(self, *, archived: bool = False, project_id: int | None = None) -> ObservableList:
        """Top-level conversations, optionally scoped to one project."""
        from server.models.enums.session_enums import SessionType

        model = self._model()
        keys = [f"{root_key(model)}@is_archived:{str(archived).lower()}"]
        queryset = model.objects.filter(
            parent_session__isnull=True,
            session_type=SessionType.SESSION,
            is_archived=archived,
        )
        if project_id is not None:
            queryset = queryset.filter(parent_project_id=project_id)
            keys = [f"{root_key(model)}@project:{project_id}@is_archived:{str(archived).lower()}"]
        return self._list(
            queryset.select_related(
                "latest_session_version__agent",
                "latest_session_version__workspace",
                "parent_project",
            ).order_by("-is_pinned", "-last_active_at", "-created_at"),
            *keys,
        )

    def children(self, parent_session_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(parent_session_id=parent_session_id)
            .select_related("latest_session_version__agent", "latest_session_version__workspace")
            .order_by("-is_pinned", "-last_active_at"),
            relation_key(model, "parent_session", parent_session_id),
        )

    def by_project(self, project_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(parent_project_id=project_id).order_by("-last_active_at"),
            relation_key(model, "parent_project", project_id),
        )

    def by_pk(self, pk: int) -> ObservableList:
        model = self._model()
        return self._list(model.objects.filter(pk=pk), pk_key(model, pk))

    def active_subagent_count(self) -> ObservableValue:
        from server.models.enums.session_enums import SessionType

        model = self._model()
        count = model.objects.filter(
            parent_session__isnull=False,
            is_active=True,
            session_type=SessionType.SESSION,
        ).count()
        return self._value(count, "SessionModel@is_active:true")