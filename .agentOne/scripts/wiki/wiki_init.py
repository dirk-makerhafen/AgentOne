"""
Spawn a wiki subagent session.

Creates an async subagent of type ``wiki``. The returned ``session_pk`` is
used by the companion tools (wiki_ingest, wiki_query, wiki_lint) to
send commands to this wiki session.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.session.session import Session
from server.models.workspace import WorkspaceModel


def wiki_init(session: Session, folder: str | None = None) -> dict[str, Any]:
    """
    Spawn a wiki_init subagent session.

    Args:
        session: The calling agent's session (bound automatically).
        folder: Optional wiki root path. otherwise callers workingdir is used.

    Returns:
        A dict with key ``session_pk`` — the pk of the new wiki_init session.
    """
    subagent_version = session.get_subagent("wiki")
    if not subagent_version:
        return {"error": "wiki agent not found"}

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

    parts = [{"type": "message", "content_type": "text", "content": f"New session created, create basic folders if needed"}]
    child_session.add_user_message(parts=parts)

    return {
        "session_pk": child_session.model.pk,
        "message": f"Wiki '{session_name}' started (session {child_session.model.pk})",
    }
