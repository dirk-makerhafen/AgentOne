
from __future__ import annotations
from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType, MessagePartType, MessageRole
from server.models.message import Message
from server.models.sessions.session import SessionModel


def _message_text(message: Any) -> str:
    """Render a result Message's MESSAGE parts to plain text (JSON-safe)."""
    if message is None or isinstance(message, str):
        return message or ""
    if isinstance(message, Message):
        return "".join(
            str(part.to_string())
            for part in message.parts.filter(type=MessagePartType.MESSAGE).order_by("pk")
        )
    return str(message)


def ingest_subagent_result(_session: Session, child_session_pk: int, summary: str, result: Message) -> Any:
    """
    Wait for a subagent's TaskCall to complete, then inject the child's last
    assistant message into *_session* (the parent) and optionally trigger
    process_turn.

    Args:
        _session: The parent session (bound automatically).
        child_session_pk: PK of the child's SessionModel.
        summary: One-sentence task summary.
        result: The resolved result Message from the child's task call.

    Returns:
        The AgentTaskCall from :meth:`Session.add_user_message` — the
        ``process_turn`` chain when delivery is immediate (framework
        auto-awaits recursively), otherwise the persist-only call.
    """
    child_session_model = SessionModel.objects.get(pk=child_session_pk)
    child_session = Session(session_model=child_session_model)

    # template_data must be JSON-safe: a runtime Agent / Message cannot be
    # serialised into GenericContent (nor Celery kwargs), so pass plain values.
    message_spec = {
        "role": MessageRole.USER,
        "parts": [
            {
                "type": MessagePartType.MESSAGE,
                "content_type": MessageContentType.TEMPLATE,
                "content": "A task was finished by subagent '{{child_agent.name}}' session #{{child_session_pk}}\nTask: {{task_summary}}\nResult: {{result}}",
                "template_data": dict(
                    child_agent={"name": child_session.agent.name},
                    child_session_pk=child_session_pk,
                    task_summary=summary,
                    result=_message_text(result),
                ),
            }
        ],
    }

    return _session.add_user_message(
        message_spec,
        execute_turn=_session.subagentResultDelivery == "immediate",
    )
