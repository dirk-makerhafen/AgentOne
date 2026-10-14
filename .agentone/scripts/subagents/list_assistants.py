
from __future__ import annotations

from typing import Any

from runtime.session.session import Session


def list_assistants(_session: Session) -> dict[str, Any]:
    """List the framework-internal assistant agents you can call.

    Internal assistants (``project_assistant``, ``skills_assistant``,
    ``workspace_assistant``, ...) are hidden from normal delegation —
    ``get_available_agents`` does not show them. This tool returns their
    names plus which domain each one manages (``skills``, ``agents``,
    ``projects``, ``workspaces``, ``workitems``, ``cronjobs``) and whether
    it handles ONE item (``singular``) or the COLLECTION in a scope
    (``plural``). Use ``call_assistant`` to send one of them a task.

    Every pair exists twice: once global (e.g. ``skills_assistant`` working
    in ``~/.agentone/skills/``) and once per project/workspace scope — the
    scope is picked via ``call_assistant``'s ``project_path``/``context_path``
    arguments, or inherited from your session.

    Args:
        (none besides _session, which is bound automatically).

    Returns:
        ``{"assistants": [{"name": str, "domain": str, "kind": str,
        "description": str}, ...]}`` sorted by name.
        On error: ``{"error": str}``.
    """
    try:
        from runtime.agents.agents import Agents
        from runtime.cron.crons import Cronjobs
        from runtime.project.projects import Projects
        from runtime.skill.skills import Skills
        from runtime.workitems.workitems import Workitems
        from runtime.workspace.workspaces import Workspaces

        assistants: list[dict[str, Any]] = []
        for cls in (Skills, Agents, Projects, Workspaces, Workitems, Cronjobs):
            singular, plural = cls.ASSISTANT_NAMES
            assistants.append(_describe(singular, cls.DOMAIN, "singular"))
            assistants.append(_describe(plural, cls.DOMAIN, "plural"))
        assistants.sort(key=lambda entry: entry["name"])
        return {"assistants": assistants}
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return {"error": f"Could not list assistants: {exc}"}


def _describe(name: str, domain: str, kind: str) -> dict[str, Any]:
    """Describe one assistant; missing rows yield blanks, never raises."""
    from server.models.agents.agent import AgentModel

    description = ""
    try:
        model = AgentModel.objects.filter(name=name).first()
        if model is not None:
            description = model.get_runtime().description or ""
    except Exception:  # pylint: disable=broad-exception-caught
        description = ""
    return {"name": name, "domain": domain, "kind": kind, "description": description}
