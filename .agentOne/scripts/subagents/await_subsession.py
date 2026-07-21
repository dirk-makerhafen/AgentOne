
from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from server.models.tasks.agent_task_call import AgentTaskCall


def await_subsession(session: Session, sessionname: str) -> dict[str, Any]:
    """Wait for a subsession's latest reply to arrive.

    Use this after sending a non-blocking message
    (``message_subsession(blocking=False)``) when you later need the result.
    Blocks until the subsession's most recent ``ingest_user_message`` task
    finishes.  The ``result`` field will contain the reply message dict.

    If no message has been sent to this subsession yet, returns an error.

    Args:
        sessionname: Name of the subsession to wait for.

    Returns:
        On success:
            ``{"result": {message dict}, "session_name": str}``
        On error:
            ``{"error": "Subsession '<name>' not found"}`` or
            ``{"error": "No pending work", "session_name": str}``
    """
    try:
        child_model = SessionModel.objects.get(parent_session=session.model, name=sessionname)
    except SessionModel.DoesNotExist:
        return {"error": f"Subsession '{sessionname}' not found"}

    taskcall = AgentTaskCall.objects.filter(
        session=child_model,
        task_definition__name="ingest_user_message",
    ).order_by("-created_at").first()

    if not taskcall:
        return {"error": "No pending work", "session_name": sessionname}

    return {"result": taskcall, "session_name": sessionname}
