"""
Sync barrier — blocks until one or more spawned subagents complete.

Finds the latest ``ingest_user_message`` TaskCall for each child session,
waits for it to resolve via ``get_result``, and returns the output text.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.message import Message


def await_subagents(session: Session, session_pks: list[int]) -> dict[str, Any]:
    """
    Wait for one or more spawned subagent sessions to complete.

    Blocks until every session in *session_pks* has finished its current
    turn (the ``ingest_user_message`` chain has resolved).  Returns the
    text output of each subagent's final assistant message.

    Args:
        session: The calling agent's session (bound automatically).
        session_pks: List of child session pks to wait for.

    Returns:
        A dict with key ``results`` — a list of per-session dicts:
        ``{session_pk, output, turn_count, error?}``.
    """
    results: list[dict[str, Any]] = []
    for spk in session_pks:
        try:
            child_model = SessionModel.objects.get(pk=spk)
        except SessionModel.DoesNotExist:
            results.append({"session_pk": spk, "error": "not found"})
            continue

        child_session = Session(session_model=child_model)

        # Find the latest ingest_user_message TaskCall for this child
        taskcall = AgentTaskCall.objects.filter(
            session=child_model,
            task_definition__name="ingest_user_message",
        ).order_by("-created_at").first()

        if not taskcall:
            results.append({"session_pk": spk, "error": "no pending work", "turn_count": 0})
            continue

        # Block until the taskcall chain resolves
        try:
            resolved = taskcall.get_result(timeout=None, recursive=True)
        except Exception as exc:
            results.append({"session_pk": spk, "error": str(exc)})
            continue

        # Extract text from the resolved Message
        if isinstance(resolved, Message):
            text_parts = []
            for part in resolved.parts.all():
                if part.type == "message":
                    content = part.content
                    text = content.get() if hasattr(content, "get") else str(content or "")
                    if text:
                        text_parts.append(text)
            output = "\n".join(text_parts)
        else:
            output = str(resolved) if resolved is not None else ""

        results.append({
            "session_pk": spk,
            "output": output,
            "turn_count": child_model.turn_count,
        })

    return {"results": results}
