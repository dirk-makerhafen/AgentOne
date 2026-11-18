"""Create a new chat session in a workspace."""
from __future__ import annotations


def create_chat(_session: Any, workspace_pk: int | None = None, agent_name: str = "general-chat", title: str | None = None, **kwargs) -> tuple[bool, dict]:
    """
    Create a new chat session in a workspace.

    Args:
        workspace_pk: Optional workspace primary key (defaults to current)
        agent_name: Agent to use (default: general-chat)
        title: Optional session title

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - session: dict with session info
        On error, result contains:
            - status: "error"
            - message: str
    """
    from server.models.workspace import WorkspaceModel
    from server.models.agents.agent import AgentModel
    from server.models.sessions.session import SessionModel
    from server.models.sessions.session_version import SessionVersionModel
    from server.models.enums.session_enums import SessionType

    target_workspace = _get_scope_workspace(_session)
    if workspace_pk:
        try:
            target_workspace = WorkspaceModel.objects.get(pk=workspace_pk)
        except WorkspaceModel.DoesNotExist:
            return (False, {"status": "error", "message": f"Workspace {workspace_pk} not found"})

    if not target_workspace:
        return (False, {"status": "error", "message": "No workspace in scope and no workspace_pk provided"})

    project = _get_scope_project(_session)
    if project and target_workspace.parent_project != project:
        if target_workspace.parent_project is not None:
            return (False, {"status": "error", "message": "Workspace not in current project scope"})

    try:
        agent = AgentModel.objects.get(name=agent_name)
    except AgentModel.DoesNotExist:
        return (False, {"status": "error", "message": f"Agent '{agent_name}' not found"})

    if not title:
        from datetime import datetime
        title = f"{target_workspace.name or 'chat'} - {agent_name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    try:
        session = SessionModel.objects.create(
            name=title,
            parent_project=project,
            session_type=SessionType.SESSION,
            is_active=True,
        )

        # Create the session version with workspace
        SessionVersionModel.objects.create(
            session=session,
            agent=agent,
            workspace=target_workspace,
            version_number=0,
            description=title,
        )

        # Update session's latest_session_version
        session.latest_session_version = session.related_session_versions.first()
        session.save(update_fields=["latest_session_version"])

    except Exception as e:
        return (False, {"status": "error", "message": f"Failed to create chat session: {e}"})

    return (True, {
        "status": "success",
        "session": {
            "pk": session.pk,
            "name": session.name or title,
            "agent": agent_name,
            "workspace": target_workspace.name or target_workspace.path,
        }
    })


def _session_project(session: Any) -> Any | None:
    return session.get_project()


def _session_workspace(session: Any) -> Any | None:
    try:
        return session.workspace
    except Exception:
        return None


def _get_scope_project(session: Any) -> Any | None:
    project = _session_project(session)
    if project:
        return project
    workspace = _session_workspace(session)
    if workspace:
        try:
            return workspace.parent_project
        except Exception:
            return None
    return None


def _get_scope_workspace(session: Any) -> Any | None:
    return _session_workspace(session)