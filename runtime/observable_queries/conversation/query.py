"""Observable Query queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    pk_key,
    relation_key,
)


class QueryObservables(ObservableBase):
    @staticmethod
    def _model():
        from server.models.queries.query import Query

        return Query

    def by_session(self, session_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(session_id=session_id).order_by("created_at", "pk"),
            relation_key(model, "session", session_id),
        )

    def by_pk(self, pk: int) -> ObservableList:
        model = self._model()
        return self._list(model.objects.filter(pk=pk), pk_key(model, pk))

    def unfinished(self) -> ObservableList:
        """Queries still in flight (queued or streaming), newest first.

        Uses the bare ``Query`` key: every query write publishes it, including
        status transitions that move a row into or out of this list.
        """
        from server.models.queries.query import QueryStatus

        model = self._model()
        return self._list(
            model.objects.filter(
                status__in=(QueryStatus.WAITING, QueryStatus.ACTIVE)
            )
            .select_related(
                "session",
                "session__parent_project",
                "session__parent_session",
                "session_version__agent",
                "session_version__workspace",
                "trigger_message",
            )
            .order_by("-created_at", "-pk"),
            "Query",
        )
