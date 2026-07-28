
from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel


def message_subsession(
    _session: Session, sessionname: str, prompt: str, blocking: bool = False
) -> dict[str, Any]:
    """Send a message to a running subsession.

    The subsession must already exist (use ``start_subsession`` first).

    When *blocking* is ``True``: your turn pauses until the subsession
    responds. The ``result`` field will contain the subsession's final
    reply text (as a dict with ``content`` and other ``Message`` fields).

    When *blocking* is ``False``: returns immediately. The subsession's
    reply will be injected into your conversation as a new user message
    once processing completes (asynchronous delivery).

    See also: ``await_subsession`` to block on a non-blocked message later,
    ``start_subsession`` to create a subsession.

    Args:
        sessionname: Name of the target subsession (created via
            ``start_subsession``).
        prompt: The message text to send to the subsession.
        blocking: ``True`` to wait for the reply before continuing,
            ``False`` to submit and receive the result later asynchronously.
            Defaults to ``False``.

    Returns:
        Blocking mode (blocking=True):
            ``{"result": {message dict, with "content", "role", etc},
              "session_name": str}``
        Non-blocking mode (blocking=False):
            ``{"result": "sent", "session_name": str, "taskcall_pk": int}``
        On error:
            ``{"error": "Subsession '<name>' not found"}``
    """
    try:
        child_model = SessionModel.objects.get(parent_session=_session.model, name=sessionname)
    except SessionModel.DoesNotExist:
        return {"error": f"Subsession '{sessionname}' not found"}

    child_session = Session(session_model=child_model)

    parts = [{"type": "message", "content_type": "text", "content": prompt}]
    taskcall = child_session.add_user_message(parts=parts)

    if blocking:
        return {"result": taskcall, "session_name": sessionname}

    _session.get_task("ingest_subagent_result").delay(
        child_session_pk=child_session.model.pk,
        summary=prompt,
        result=taskcall,
    )

    return {"result": "sent", "session_name": sessionname, "taskcall_pk": taskcall.pk}
