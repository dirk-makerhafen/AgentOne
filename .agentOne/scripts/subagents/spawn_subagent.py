"""
Async subagent spawning — returns immediately with a session_pk.

The subagent starts processing in the background. The parent can later
call await_subagents, message_subagent, list_subagents, or stop_subagent.
"""

from __future__ import annotations

from time import time
from typing import Any

from runtime.session.session import Session


def spawn_subagent(session: Session, subagent_name: str, query: str) -> dict[str, Any]:
    """
    Spawn a subagent asynchronously (non-blocking).

    Creates a new child session and dispatches *query* as the initial user
    message. Returns immediately with the child session pk. The subagent
    processes in the background; use the companion tools to interact with
    it later.

    Args:
        session: The calling agent's session (bound automatically).
        subagent_name: Name of the subagent to spawn.
        query: The task description or message to send.

    Returns:
        A dict with key ``session_pk`` — the pk of the new child session.
    """
    subagent_version = session.get_subagent(subagent_name)
    if not subagent_version:
        return {"error": f"Subagent '{subagent_name}' not found"}

    name = f"p{session.model.pk}:{subagent_name}:{int(time())}"

    child_sv = subagent_version.get_or_create_session(
        name=name,
        workspace=session.workspace,
        parent_session_version=session.get_version_model(),
    )
    child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)

    parts = [{"type": "message", "content_type": "text", "content": query}]
    child_session.add_user_message(parts=parts)

    return {"session_pk": child_session.model.pk}
