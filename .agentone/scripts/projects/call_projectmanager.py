"""
Send a task message to a project's singleton project_assistant session (blocking).

Uses the framework's TaskCall auto-await: returns the AgentTaskCall from
add_user_message, which the framework resolves recursively through the
entire process_turn chain until the project_assistant produces a final
assistant Message.

The session is identified by the project path, so all callers share one
project_assistant session per project.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session
from server.models.agents.agent import AgentModel
from server.models.enums.message_enums import MessageContentType, MessagePartType
from server.models.enums.session_enums import SessionType
from server.models.workspace import WorkspaceModel


def call_projectmanager(_session: Session, project_path: str, task: str) -> dict[str, Any]:
    """
    Send a task to a project's singleton project_assistant session (blocking).

    Creates or reuses a globally-shared session named
    ``project_assistant:<project_path>``. The project_assistant agent processes
    the message and its response is returned via the auto-awaited TaskCall.

    Args:
        _session: The calling agent's session (bound automatically).
        project_path: Absolute path of the target project.
        task: The task description or message to send to the project_assistant.

    Returns:
        A dict with keys:
            - result: the resolved TaskCall (auto-awaited by framework)
            - session_pk: the project_assistant session pk for follow-up
            - error: if something went wrong
    """
    try:
        agent_model = AgentModel.objects.get(name="project_assistant")
    except AgentModel.DoesNotExist:
        return {"error": "project_assistant agent not found"}

    if not agent_model.latest_agent_version:
        return {"error": "project_assistant agent has no version"}

    session_name = f"project_assistant:{project_path}"

    workspace, ws_created = WorkspaceModel.objects.get_or_create(
        name=f"{project_path} project root",
        path=project_path,
        description="project root directory"
    )
    if ws_created:
        from runtime.events import publish_model_event

        publish_model_event(workspace, "create")

    child_session = _session.spawn_subagent(
        "project_assistant",
        name=session_name,
        description=f"Project assistant for {project_path}",
        workspace=workspace,
        session_type=SessionType.SUBSESSION,
        allow_internal=True,
    )
    if child_session is None:
        return {"error": "project_assistant agent not found"}

    parts = [{"type": MessagePartType.MESSAGE, "content_type": MessageContentType.TEXT, "content": task}]
    taskcall = child_session.add_user_message(parts)

    return {"result": taskcall, "session_pk": child_session.model.pk}
