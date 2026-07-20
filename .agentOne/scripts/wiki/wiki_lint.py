"""
Send a ``lint`` command to a running wiki session.

The wiki will health-check its vault and optionally run the archiving pass.
Use ``await_subagents`` to wait for the result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from server.models.workspace import WorkspaceModel


def wiki_lint(session: Session,   message: str | None = None, folder: str | None = None) -> dict[str, Any]:
    """
    Send a ``lint`` command to a wiki subagent .

    Args:
        session: The calling agent's session (bound automatically).
        folder: Optional wiki root path. otherwise callers workingdir is used.
        message: Optional focus instruction — narrows the lint to a specific
                 concern (e.g. "check only orphaned entity pages", "find stale
                 index.md links").

    Returns:
        A dict indicating the command was sent.
    """
    child_session, error = _resolve_wiki(session, folder)
    if error:
        return {"error": error}

    query = f"lint — {message}" if message else "lint"
    parts = [{"type": "message", "content_type": "text", "content": query}]
    child_session.add_user_message(parts=parts)

    return {"result": "sent", "session_pk": child_session.model.pk, "command": "lint", "focus": message}


def _resolve_wiki(session: Session, folder: str | None = None):
    subagent_version = session.get_subagent("wiki")
    if not subagent_version:
        return  None, {"error": "wiki agent not found"}

    if not folder:
        folder = session.workspace.path
    else:
        if not Path(folder).is_absolute():
            folder = (Path(session.workspace.path) /  Path(folder)).resolve().as_posix()

    workspace, _ = WorkspaceModel.objects.get_or_create(
        name=f"Wiki: '{folder}'", 
        path=folder,
        description=f"Wiki '{folder}' root directory"
    )
   
    session_name = f"Wiki:'{folder}':Main"
    child_sv = subagent_version.get_or_create_session(
        name=session_name,
        description= f"Wiki '{folder}' Main Session",
        workspace=workspace,
        parent_session_version=session.get_version_model(),
    )
    child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)
    return child_session, None
