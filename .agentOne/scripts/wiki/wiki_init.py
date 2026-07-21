from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.session.session import Session
from server.models.sessions.session_version import SessionVersionModel
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


def wiki_init(session: Session, folder: str | None = None) -> dict[str, Any]:
    """Spawn a wiki subagent session.

    Creates or reuses a named background session for the ``wiki`` agent.
    An initialisation command is sent automatically.

    When *blocking* is ``True`` the result of the init command is returned
    directly.  When *blocking* is ``False`` (default) the init command is
    dispatched asynchronously and its result is delivered back later.

    Args:
        session: The calling agent's session (bound automatically).
        folder: Optional wiki root path. Defaults to the caller's working
            directory.
    Returns:
        On success:
            ``{"session_pk": int, "session_name": str, ...}``
    """
    workspace, session_name = _workspace_and_name(session, folder)

    start = session.get_task("start_subsession")
    result = start.call(
        agentname="wiki",
        sessionname=session_name,
        prompt=f"Wiki '{folder or session.workspace.path}' Main Session",
    )
    if "error" in result:
        return result

    # Override the default workspace with the wiki-specific one.
    session_pk = result["session_pk"]
    sv = SessionVersionModel.objects.filter(session__pk=session_pk).first()
    if sv and sv.workspace_id != workspace.pk:
        sv.workspace = workspace
        sv.save(update_fields=["workspace"])

    # Send the init command.
    message_subsession = session.get_task("message_subsession")
    msg_result = message_subsession.delay(
        sessionname=session_name,
        prompt="New wiki session created, create basic folders if needed",
        blocking=True,
    )
    return {
        "result": msg_result,
        "session_pk": session_pk,
        "session_name": session_name,
    }
