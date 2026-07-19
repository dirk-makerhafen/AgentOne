"""
Spawn a brain subagent session.

Creates an async subagent of type ``brain``. The returned ``session_pk`` is
used by the companion tools (brain_ingest, brain_query, brain_lint) to
send commands to this brain session.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.workspace import WorkspaceModel


def brain_init(session: Session, brain_name: str | None = None, folder: str | None = None) -> dict[str, Any]:
    """
    Spawn a brain subagent session.

    Args:
        session: The calling agent's session (bound automatically).
        brain_name: A name for this brain session. Auto-generated if omitted.
        folder: Optional vault root path. otherwise callers workingdir is used.

    Returns:
        A dict with key ``session_pk`` — the pk of the new brain session.
    """
    subagent_version = session.get_subagent("brain")
    if not subagent_version:
        return {"error": "Brain agent not found"}
    if not brain_name:
        brain_name = f"p{session.model.pk}:brain"
    description = f"Brain session for Session PK {session.model.pk}"
    if folder:
        workspace, _ = WorkspaceModel.objects.get_or_create(
            name=f"Brain '{brain_name}' root", 
            path=folder,
            description=f"{description} root directory"
        )
    else:
        workspace = session.workspace

    child_sv = subagent_version.get_or_create_session(
        name=brain_name,
        description=description,
        workspace=workspace,
        parent_session_version=session.get_version_model(),
    )
    child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)

    parts = [{"type": "message", "content_type": "text", "content": f"New session created, create basic folders if needed"}]
    child_session.add_user_message(parts=parts)

    return {
        "session_pk": child_session.model.pk,
        "message": f"Brain '{brain_name}' started (session {child_session.model.pk})",
    }
