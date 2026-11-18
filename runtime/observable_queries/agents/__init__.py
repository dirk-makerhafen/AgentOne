"""Agent & Skill observable queries."""
from __future__ import annotations

from runtime.observable_queries.agents.agent import AgentObservables
from runtime.observable_queries.agents.agent_version import AgentVersionObservables
from runtime.observable_queries.agents.skill import SkillObservables
from runtime.observable_queries.agents.skill_version import SkillVersionObservables

__all__ = [
    "AgentObservables",
    "AgentVersionObservables",
    "SkillObservables",
    "SkillVersionObservables",
]