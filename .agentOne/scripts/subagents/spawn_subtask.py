
from __future__ import annotations

from time import time
from typing import Any

from runtime.session.session import Session
from server.models.enums.message_enums import MessageContentType
from server.models.message import Message


def spawn_subtask(session: Session, prompt: str, blocking: bool = False) -> dict[str, Any]:
    """Fork yourself — create a child session running the same agent to do a task.

    The child runs as a separate session with your agent's configuration.  It
    **inherits the full chat history** up to the current point in *your*
    conversation — the child can see everything that was said before the fork.

    When *blocking* is ``True``: your turn pauses until the subtask finishes.
    The ``result`` field will contain the subtask's final reply (a message
    dict with ``content``, ``role``, etc.).

    When *blocking* is ``False``: returns immediately. The subtask's reply
    will be injected back into your conversation as a new user message once
    it completes (asynchronous delivery).

    See also: ``delegate_task`` (same concept but lets you choose a different
    agent), ``start_subsession`` (for persistent named background sessions).

    Args:
        prompt: The task description for the subtask to execute.
        blocking: ``True`` to wait for the result, ``False`` to submit and
            receive the result later asynchronously. Defaults to ``False``.

    Returns:
        Blocking mode (blocking=True):
            ``{"result": {message dict}, "session_pk": int}``
        Non-blocking mode (blocking=False):
            ``{"result": "spawned", "session_pk": int}``
        On error:
            ``{"error": str}``
    """
    agent_version = session.agent.get_version_model()
    if not agent_version:
        return {"error": "Current agent version not found"}

    session_name = f"p{session.model.pk}:task:{int(time())}"
    child_sv = agent_version.get_or_create_session(
        name=session_name,
        description=prompt,
        workspace=session.workspace,
        parent_session_version=session.get_version_model(),
    )
    child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)

    # Prepend a system message explaining the fork context.
    # Link prev_message to the parent's last message so the child sees the
    # conversation history at the point of the fork.
    parent_last = session.get_messages().filter(next_messages=None).last()
    child_version = child_session.get_version_model()
    fork_msg = Message.objects.create(role="user", session_version=child_version, prev_message=parent_last)
    fork_msg.add_part(
        type="message",
        content_type=MessageContentType.TEXT,
        content=(f"You have been forked from parent session #{session.model.pk} of agent '{session.agent.name}'. Your task:"),
    )

    parts = [{"type": "message", "content_type": "text", "content": prompt}]
    taskcall = child_session.add_user_message(parts=parts)

    if blocking:
        return {"result": taskcall, "session_pk": child_session.model.pk}

    session.get_task("ingest_subagent_result").delay(
        child_session_pk=child_session.model.pk,
        summary=prompt,
        result=taskcall,
    )
    return {"result": "spawned", "session_pk": child_session.model.pk}
