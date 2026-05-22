from django.db.models import QuerySet

from runtime.agents.agent import Agent
from server.models.agents.agent import AgentModel


class Agents:
    """Query interface for root-level AgentModel instances."""

    def __init__(self) -> None:
        pass

    def root(self) -> QuerySet[AgentModel]:
        """Return top-level agents (those without a parent)."""
        return AgentModel.objects.filter(
            parent_skill=None,
            parent_agent=None,
            parent_project=None,
        )
