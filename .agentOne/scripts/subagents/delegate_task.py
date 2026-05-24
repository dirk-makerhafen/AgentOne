"""
Sync subagent delegation — blocks until the subagent finishes and returns its output.

Uses the framework's TaskCall auto-await: returns the AgentTaskCall from
add_user_message, which the framework resolves recursively through the
entire process_turn chain until the subagent produces a final assistant Message.
"""

from __future__ import annotations

from time import time
from typing import Any

from runtime.session.session import Session


def delegate_task(session: Session, subagent_name: str, summary:str, query: str) -> dict[str, Any]:
    """
    Delegate a task to a named subagent and wait for the result (blocking).

    Creates a new child session, sends *query* as the initial user message,
    and returns the TaskCall that the framework auto-awaits.

    Args:
        session: The calling agent's session (bound automatically).
        subagent_name: Name of the subagent to delegate to.
        summary: One sencence task summary.
        query: The full task description or message to send.

    Returns:
        A dict with keys:
            - result: the resolved TaskCall (auto-awaited by framework)
            - session_pk: the child session pk for follow-up
            - error: if something went wrong
    """
    subagent_version = session.get_subagent(subagent_name)
    if not subagent_version:
        return {"error": f"Subagent '{subagent_name}' not found"}

    session_version_model = session.get_version_model()
    name = f"p{session_version_model.session.pk}:{subagent_name}:{int(time())}"

    child_sv = subagent_version.get_or_create_session(
        name=name,
        description=summary,
        workspace=session_version_model.workspace,
        parent_session_version=session_version_model,
    )
    child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)

    parts = [{"type": "message", "content_type": "text", "content": query}]
    taskcall = child_session.add_user_message(parts=parts)

    return {"result": taskcall, "session_pk": child_session.model.pk}
