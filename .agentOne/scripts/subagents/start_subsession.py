
from __future__ import annotations

from typing import Any

from runtime.session.session import Session


def start_subsession(session: Session, agentname: str, sessionname: str, prompt: str) -> dict[str, Any]:
    """Create a long-running background subsession of another agent.

    The subsession persists across turns — you can send follow-up messages
    with ``message_subsession`` and retrieve results with ``await_subsession``.
    If *sessionname* already exists, the existing subsession is returned
    instead (soft dedup — no error).

    Use this for ongoing conversations (e.g., a research assistant, a wiki,
    a coding agent).  For one-off tasks, use ``delegate_task`` (other agent)
    or ``spawn_subtask`` (same agent) instead.

    Args:
        agentname: Name of the agent to run. Run ``get_available_agents`` to
            see valid names.
        sessionname: Unique name for this subsession. Reusing a name returns
            the existing session. Use this name in all subsequent calls.
        prompt: Description or initial instruction. This becomes the
            subsession's session description.

    Returns:
        On success: ``{"session_pk": int, "session_name": str}``.
        On error: ``{"error": "Agent '<name>' not found"}``.
    """
    subagent_version = session.get_subagent(agentname)
    if not subagent_version:
        return {"error": f"Agent '{agentname}' not found"}

    child_sv = subagent_version.get_or_create_session(
        name=sessionname,
        description=prompt,
        workspace=session.workspace,
        parent_session_version=session.get_version_model(),
    )
    child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)

    return {
        "session_pk": child_session.model.pk,
        "session_name": sessionname,
    }
