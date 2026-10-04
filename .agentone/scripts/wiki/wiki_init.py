from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.session.session import Session
from server.models.enums.session_enums import SessionType
from server.models.sessions.session_version import SessionVersionModel
from server.models.workspace import WorkspaceModel


def _workspace_and_name(_session: Session, folder: str | None = None) -> tuple[WorkspaceModel, str]:
    if not folder:
        folder = _session.workspace.path
    else:
        p = Path(folder)
        if not p.is_absolute():
            folder = (Path(_session.workspace.path) / p).resolve().as_posix()
    workspace, ws_created = WorkspaceModel.objects.get_or_create(
        name=f"wiki:{folder}",
        path=folder,
        description=f"wiki '{folder}' root directory",
    )
    if ws_created:
        from runtime.events import publish_model_event

        publish_model_event(workspace, "create")
    return workspace, f"wiki:{folder}:main"


def wiki_init(_session: Session, folder: str | None = None) -> dict[str, Any]:
    """Spawn a wiki subagent session.

    Creates or reuses a named background session for the ``wiki`` agent.
    An initialisation command is sent automatically.

    When *blocking* is ``True`` the result of the init command is returned
    directly.  When *blocking* is ``False`` (default) the init command is
    dispatched asynchronously and its result is delivered back later.

    Args:
        _session: The calling agent's session (bound automatically).
        folder: Optional wiki root path. Defaults to the caller's working
            directory.
    Returns:
        On success:
            ``{"session_pk": int, "session_name": str, ...}``
    """
    workspace, session_name = _workspace_and_name(_session, folder)

    subagent_version = _session.get_subagent("wiki")
    if not subagent_version:
        return {"error": f"Agent 'wiki' not found"}

    child_sv = subagent_version.get_or_create_session(
        name=session_name,
        description=f"Wiki '{folder or _session.workspace.path}' main _session.",
        workspace=workspace,
        parent_session_version=_session.get_version_model(),
        session_type=SessionType.SUBSESSION,
    )
    child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)

    # Send the init command.
    message_subsession = _session.get_tool("message_subsession")
    msg_result = message_subsession.delay(
        sessionname=session_name,
        prompt="New wiki session created, create basic files and folders if needed. git init the folder if new, commit your work as first commit. Dont start to automatically ingest data yet, just prepare.",
        blocking=True,
    )
    return {
        "result": msg_result,
        "session_name": session_name,
    }
