"""Send a task message to a framework-internal assistant session (blocking).

The former per-domain ``*_assistant`` pairs were consolidated into AgentOne.
The runtime collection wrappers resolve the scope (global vs project) and the
bound workspace; ``Sessions.assistant_session`` is the spawn choke point. Run
``list_assistants`` to see the available name.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session


def call_assistant(
    _session: Session,
    name: str,
    task: str,
    context_path: str | None = None,
    project_path: str | None = None,
) -> dict[str, Any]:
    """
    Send a task to a framework-internal assistant session (blocking).

    Creates or reuses a shared AgentOne session per scope, named
    ``AgentOne - <scope-label>``. The assistant processes the message and its
    response is returned via the auto-awaited TaskCall.

    Scope resolution (first match wins):

    1. ``project_path`` matches a registered project (by path or manifest
       dir) → that project's scope. Unmatched paths fall back to a global
       scope bound to a workspace at that path.
    2. ``context_path`` → workspace override at that path; the project
       scope is inherited from your session.
    3. Neither → your session's scope is inherited.

    Args:
        _session: The calling agent's session (bound automatically).
        name: Internal assistant name — ``AgentOne`` (see ``list_assistants``).
        task: The task description or message to send to the assistant.
        context_path: Optional absolute directory the assistant session is
            bound to (a workspace record is created when missing).
        project_path: Optional absolute path of a registered project to
            scope the assistant to.

    Returns:
        ``{"result": taskcall, "session_pk": int, "scope": {...}}`` or
        ``{"error": str}``.
    """
    from runtime.session.sessions import Sessions
    from runtime.workspace.workspaces import Workspaces

    assistant = (name or "").strip()
    if not assistant:
        return {"error": "You must provide an assistant name (see list_assistants)"}
    if not (task or "").strip():
        return {"error": "You must provide a task to send to the assistant"}

    if assistant != "AgentOne":
        return {
            "error": (
                f"Assistant '{assistant}' is not a registered internal assistant "
                "(see list_assistants)"
            )
        }

    project: Any = None
    override: str | None = None
    if project_path:
        found = _resolve_project(project_path)
        if found is not None:
            project = found
        else:
            # Unregistered path: global scope bound to a workspace there.
            override = project_path
    else:
        project = _session.get_project()
    if context_path:
        override = context_path

    workspace = None
    if override:
        target = override.strip().rstrip("/")
        workspace = Workspaces.ensure_source_scope(
            f"{target} assistant scope", target,
            "assistant scope override",
            parent_project=project,
        )
        scope_label = target.rsplit("/", 1)[-1] or "global"
    else:
        workspace = _caller_workspace(_session)
        if not _workspace_in_project(workspace, project):
            workspace = None
        scope_label = getattr(project, "name", "") or _workspace_label(workspace)

    child = Sessions().assistant_session(
        "AgentOne", project=project, workspace=workspace, caller=_session,
        scope_label=scope_label,
    )
    if child is None:
        return {"error": "AgentOne could not be resolved or spawned"}
    return _send(child, assistant, task, project, workspace)


def _caller_workspace(_session: Any) -> Any | None:
    """Return the calling session's bound workspace, or *None*."""
    try:
        return _session.workspace
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _workspace_in_project(workspace: Any, project: Any) -> bool:
    """True when *workspace* belongs to *project* (or has no owner yet)."""
    if project is None:
        return True
    candidate = workspace
    model = getattr(workspace, "model", None)
    if model is not None:
        candidate = model
    try:
        owner = getattr(candidate, "parent_project", None)
        owner_pk = getattr(owner, "pk", None)
        if owner_pk is None:
            owner_pk = getattr(candidate, "parent_project_id", None)
    except Exception:  # pylint: disable=broad-exception-caught
        owner_pk = None
    return owner_pk in (None, getattr(project, "pk", None))


def _workspace_label(workspace: Any) -> str:
    """Return a readable scope label for *workspace*."""
    name = (getattr(workspace, "name", "") or "").strip()
    if name:
        return name
    path = (getattr(workspace, "path", "") or "").strip().rstrip("/")
    return path.rsplit("/", 1)[-1] if path else "global"


def _send(child: Any, assistant: str, task: str, project: Any, workspace: Any) -> dict[str, Any]:
    """Deliver *task* to the assistant session (blocking TaskCall)."""
    from server.models.enums.message_enums import MessageContentType, MessagePartType

    parts = [{
        "type": MessagePartType.MESSAGE,
        "content_type": MessageContentType.TEXT,
        "content": task,
    }]
    try:
        taskcall = child.add_user_message(parts)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return {"error": f"Assistant '{assistant}' did not accept the task: {exc}"}
    try:
        ws_path = workspace.path if workspace is not None else None
    except Exception:  # pylint: disable=broad-exception-caught
        ws_path = None
    try:
        project_name = project.name if project is not None else None
    except Exception:  # pylint: disable=broad-exception-caught
        project_name = None
    return {
        "result": taskcall,
        "session_pk": child.model.pk,
        "scope": {
            "kind": "project" if project is not None else "global",
            "project": project_name,
            "workspace": ws_path,
        },
    }


def _resolve_project(project_path: str) -> Any | None:
    """Return the registered project for *project_path*, or *None*."""
    from server.models.project import Project

    wanted = (project_path or "").strip().rstrip("/")
    if not wanted:
        return None
    project = (
        Project.objects.filter(agentone_dir=wanted).first()
        or Project.objects.filter(main_workspace__path=wanted).first()
    )
    if project is None:
        # Legacy fallback: match the resolved manifest dir (covers rows
        # created before manifest_dir existed).
        for candidate in Project.objects.all():
            try:
                if candidate.get_agentone_dir().as_posix().rstrip("/") == wanted:
                    project = candidate
                    break
            except Exception:  # pylint: disable=broad-exception-caught
                continue
    return project
