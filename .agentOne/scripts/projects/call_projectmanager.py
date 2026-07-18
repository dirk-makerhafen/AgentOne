"""
Send a task message to a project's singleton projectmanager session (blocking).

Uses the framework's TaskCall auto-await: returns the AgentTaskCall from
add_user_message, which the framework resolves recursively through the
entire process_turn chain until the projectmanager produces a final
assistant Message.

The session is identified by the project path, so all callers share one
projectmanager session per project.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.agents.agent import AgentModel
from server.models.workspace import WorkspaceModel


def call_projectmanager(session: Session, project_path: str, task: str) -> dict[str, Any]:
    """
    Send a task to a project's singleton projectmanager session (blocking).

    Creates or reuses a globally-shared session named
    ``projectmanager:<project_path>``. The projectmanager agent processes
    the message and its response is returned via the auto-awaited TaskCall.

    Args:
        session: The calling agent's session (bound automatically).
        project_path: Absolute path of the target project.
        task: The task description or message to send to the projectmanager.

    Returns:
        A dict with keys:
            - result: the resolved TaskCall (auto-awaited by framework)
            - session_pk: the projectmanager session pk for follow-up
            - error: if something went wrong
    """
    try:
        agent_model = AgentModel.objects.get(name="projectmanager")
    except AgentModel.DoesNotExist:
        return {"error": "projectmanager agent not found"}

    agent_version = agent_model.latest_agent_version
    if not agent_version:
        return {"error": "projectmanager agent has no version"}

    session_name = f"projectmanager:{project_path}"

    session_version_model = session.get_version_model()
    workspace, _ = WorkspaceModel.objects.get_or_create(
        name=f"{project_path} project root", 
        path=project_path, 
        description="project root directory"
    )

    child_sv = agent_version.get_or_create_session(
        name=session_name,
        description=f"Project manager for {project_path}",
        workspace=workspace,
        parent_session_version = session_version_model,
    )
    child_session = Session(
        session_model=child_sv.session,
        pinned_session_version=child_sv,
    )

    parts = [{"type": "message", "content_type": "text", "content": task}]
    taskcall = child_session.add_user_message(parts=parts)

    return {"result": taskcall, "session_pk": child_session.model.pk}
