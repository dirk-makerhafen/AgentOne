"""Observable TerminalSession queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    relation_key,
)


class TerminalObservables(ObservableBase):
    def by_session(self, session_id: int) -> ObservableList:
        from server.models.terminal import TerminalSession

        return self._list(
            TerminalSession.objects.filter(session_id=session_id).order_by("created_at"),
            relation_key(TerminalSession, "session", session_id),
        )