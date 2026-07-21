from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.workspace import WorkspaceModel


def _workspace_and_name(session: Session, folder: str | None = None) -> tuple[WorkspaceModel, str]:
    if not folder:
        folder = session.workspace.path
    else:
        p = Path(folder)
        if not p.is_absolute():
            folder = (Path(session.workspace.path) / p).resolve().as_posix()
    workspace, _ = WorkspaceModel.objects.get_or_create(
        name=f"Wiki:{folder}",
        path=folder,
        description=f"Wiki '{folder}' root directory",
    )
    return workspace, f"Wiki:{folder}:Main"


def wiki_query(session: Session, question: str, folder: str | None = None, blocking: bool = False) -> dict[str, Any]:
    """Send a question to the memory wiki.

    When *blocking* is ``True`` the answer is returned directly.
    When *blocking* is ``False`` (default) the question is dispatched
    asynchronously and the answer is delivered back later.

    Args:
        session: The calling agent's session (bound automatically).
        question: The question to ask the wiki.
        folder: Optional wiki root path. Defaults to the caller's working
            directory.
        blocking: ``True`` to wait for the answer, ``False`` to submit and
            receive the answer later. Defaults to ``False``.

    Returns:
        A dict indicating the command was sent.
    """
    _, session_name = _workspace_and_name(session, folder)
    prompt = f"query {question}"

    message_subsession = session.get_task("message_subsession")
    return  message_subsession.delay(sessionname=session_name, prompt=prompt, blocking=blocking)
   