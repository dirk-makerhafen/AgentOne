"""Observable AgentVersionModel queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    relation_key,
)


class AgentVersionObservables(ObservableBase):
    def by_agent(self, agent_id: int) -> ObservableList:
        from server.models.agents.agent_version import AgentVersionModel

        return self._list(
            AgentVersionModel.objects.filter(agent_id=agent_id).order_by("-created_at"),
            relation_key(AgentVersionModel, "agent", agent_id),
        )