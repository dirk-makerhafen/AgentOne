"""
Send an ``ingest`` command to a running wiki session.

The message is appended to the wiki's conversation; the wiki processes it
asynchronously. Use ``await_subagents`` to wait for completion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.session.session import Session
from server.models.sessions.session import SessionModel
from server.models.workspace import WorkspaceModel


def wiki_ingest(session: Session, source: str, folder: str | None = None) -> dict[str, Any]:
    """
    Send an ``ingest`` command to a wiki subagent session.

    Args:
        session: The calling agent's session (bound automatically).
        source: File path or URL to ingest.
        folder: Optional wiki root path. otherwise callers workingdir is used.

    Returns:
        A dict indicating the command was sent.
    """
    child_session, error = _resolve_wiki(session, folder)
    if error:
        return {"error": error}

    parts = [{"type": "message", "content_type": "text", "content": f"ingest {source}"}]
    child_session.add_user_message(parts=parts)

    return {"result": "sent", "session_pk": child_session.model.pk, "command": "ingest", "source": source}


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
