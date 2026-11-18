"""Observable Response queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    pk_key,
    relation_key,
)


class ResponseObservables(ObservableBase):
    @staticmethod
    def _model():
        from server.models.queries.response import Response

        return Response

    def by_session(self, session_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(session_id=session_id).order_by("created_at", "pk"),
            relation_key(model, "session", session_id),
        )

    def by_query(self, query_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(query_id=query_id),
            relation_key(model, "query", query_id),
        )

    def by_pk(self, pk: int) -> ObservableList:
        model = self._model()
        return self._list(model.objects.filter(pk=pk), pk_key(model, pk))