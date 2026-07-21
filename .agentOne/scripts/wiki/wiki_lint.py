from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.session.session import Session
from server.models.sessions.session_version import SessionVersionModel
from server.models.workspace import WorkspaceModel


def _session_name(folder: str) -> str:
    WorkspaceModel.objects.get_or_create(
        name=f"wiki:{folder}",
        path=folder,
        description=f"wiki '{folder}' root directory",
    )
    return f"wiki:{folder}:Main"


def _resolve_folder(session: Session, folder: str | None = None) -> str | None:
    if folder is not None:
        p = Path(folder)
        if not p.is_absolute():
            folder = (Path(session.workspace.path) / p).resolve().as_posix()
        return folder

    brain_paths = list(
        SessionVersionModel.objects.filter(
            parent_session_version=session.get_version_model(),
            agent__name="brain",
            workspace__isnull=False,
        ).values_list("workspace__path", flat=True).distinct()
    )
    if len(brain_paths) == 1:
        return brain_paths[0]
    return None


def wiki_lint(session: Session, message: str | None = None, folder: str | None = None, blocking: bool = False) -> dict[str, Any]:
    """Send a ``lint`` command to a wiki subagent.

    When *blocking* is ``True`` the lint result is returned directly.
    When *blocking* is ``False`` (default) the command is dispatched
    asynchronously and the result is delivered back later.

    Args:
        session: The calling agent's session (bound automatically).
        message: Optional focus instruction — narrows the lint to a
            specific concern.
        folder: Optional wiki root path. When omitted and there is exactly
            one subsession with agent type ``brain``, its workspace is used.
        blocking: ``True`` to wait for the result, ``False`` to submit and
            receive the result later. Defaults to ``False``.

    Returns:
        A dict indicating the command was sent.
    """
    resolved = _resolve_folder(session, folder)
    if resolved is None:
        brain_paths = list(
            SessionVersionModel.objects.filter(
                parent_session_version=session.get_version_model(),
                agent__name="brain",
                workspace__isnull=False,
            ).values_list("workspace__path", flat=True).distinct()
        )
        if not brain_paths:
            return {"error": "no brain folder found — no subsessions with agent type 'brain' exist"}
        path_list = "\n".join(f"  - {p}" for p in brain_paths)
        return {"error": f"more than one brain folder found:\n{path_list}\nfolder parameter mandatory in this case"}

    session_name = _session_name(resolved)
    prompt = f"lint {message}" if message else "lint"

    message_subsession = session.get_task("message_subsession")
    return message_subsession.delay(sessionname=session_name, prompt=prompt, blocking=blocking)
