
from __future__ import annotations

from typing import Any

from runtime.session.session import Session


def get_available_agents(_session: Session) -> dict[str, Any]:
    """List every agent you can delegate tasks or subsessions to.

    The returned ``name`` values are the valid inputs for the *agentname*
    parameter of ``start_subsession`` and ``delegate_task``.

    Args:
        (none besides _session, which is bound automatically).

    Returns:
        ``{"agents": [{
            "name": str,
            "description": str,
            "version": int,
            "pk": int
        }, ...]}``

    Example agent names: ``"baseagent"``, ``"agentone"`` (these are the
    two default agents).  Other names depend on what's installed.
    """
    agents: list[dict[str, Any]] = []
    for av in _session.allowedSubagents:
        agents.append({
            "name": av.agent.name,
            "description": av.description,
            "version": av.version_number,
            "pk": av.pk,
        })

    return {"agents": agents}
