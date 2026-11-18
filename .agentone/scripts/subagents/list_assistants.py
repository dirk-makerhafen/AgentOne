"""List the framework assistant available for internal tasks.

The former per-domain ``*_assistant`` / ``*s_assistant`` pairs were
consolidated into the single ``AgentOne`` agent. Framework administration now
goes through its agent-local ``admin_tool`` (and work items through the
dedicated ``workitems.*`` tools), so there is only one internal assistant to
discover.
"""
from __future__ import annotations

from typing import Any

from runtime.session.session import Session


def list_assistants(_session: Session) -> dict[str, Any]:
    """List the framework-internal assistant you can call.

    Only ``AgentOne`` remains: it replaced the old agent/skill/project/
    workspace/cronjob/workitem assistant pairs. Inspect framework state with
    ``admin_tool(scope=..., action="help")`` inside that agent.

    Args:
        (none besides _session, which is bound automatically).

    Returns:
        ``{"assistants": [{"name": str, "domain": str, "kind": str,
        "description": str}, ...]}`` or ``{"error": str}``.
    """
    try:
        from server.models.agents.agent import AgentModel

        model = AgentModel.objects.filter(name="AgentOne").first()
        description = ""
        if model is not None:
            try:
                description = model.get_runtime().description or ""
            except Exception:  # pylint: disable=broad-exception-caught
                description = ""
        return {"assistants": [{
            "name": "AgentOne",
            "domain": "framework",
            "kind": "singular",
            "description": description or (
                "Single framework assistant. Use admin_tool for projects, "
                "workspaces, cronjobs and agent/skill inspection."
            ),
        }]}
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return {"error": f"Could not list assistants: {exc}"}
