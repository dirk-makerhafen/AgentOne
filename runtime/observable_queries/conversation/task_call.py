"""Observable AgentTaskCall queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    pk_key,
    relation_key,
)


class TaskCallObservables(ObservableBase):
    @staticmethod
    def _model():
        from server.models.tasks.agent_task_call import AgentTaskCall

        return AgentTaskCall

    def by_session(self, session_id: int) -> ObservableList:
        model = self._model()
        return self._list(
            model.objects.filter(session_id=session_id).order_by("created_at", "pk"),
            relation_key(model, "session", session_id),
        )

    def by_pk(self, pk: int) -> ObservableList:
        model = self._model()
        return self._list(model.objects.filter(pk=pk), pk_key(model, pk))