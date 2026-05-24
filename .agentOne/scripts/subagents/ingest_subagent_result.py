
from __future__ import annotations
from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType
from server.models.message import Message
from server.models.sessions.session import SessionModel
from server.models.tasks.agent_task_call import AgentTaskCall


def ingest_subagent_result(session: Session, child_session_pk: int, summary: str, result: Message) -> Any:
    """
    Wait for a subagent's TaskCall to complete, then inject the child's last
    assistant message into *session* (the parent) and trigger process_turn.

    Args:
        session: The parent session (bound automatically).
        child_session_pk: PK of the child's SessionModel.
        summary: One-sentence task summary.
        result: The resolved result Message from the child's task call.

    Returns:
        The result of ``session.add_user_message(...)`` — an AgentTaskCall
        that chains to ``ingest_user_message`` → ``process_turn`` on the
        parent.  The framework auto-awaits this recursively.
    """
    child_session_model = SessionModel.objects.get(pk=child_session_pk)
    child_session = Session(session_model=child_session_model)

    session_version = session.get_version_model()
    prev_message = session.get_messages().filter(next_messages=None).last()
    message = Message.objects.create(role="user", session_version=session_version, prev_message=prev_message)
    message.add_part(
        type="message",
        content_type=MessageContentType.TEMPLATE,
        content="A task was finished by subagent '{{child_agent.name}}' session #{{child_session_pk}}\nTask: {{task_summary}}\nResult: {{result}}",
        template_data=dict(
            child_agent=child_session.agent,
            child_session_pk=child_session_pk,
            task_summary=summary,
            result=result
        )
    )

    if session.subagentResultDelivery == "immediate":
        return session.get_task("process_turn").delay(message=message)
    
