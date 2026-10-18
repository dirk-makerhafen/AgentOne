"""Send a task message to a framework-internal assistant session (blocking).

Thin tool wrapper: the ``*_assistant`` / ``*s_assistant`` pairs are owned
by the runtime collection classes (``Skills`` → ``skill(s)_assistant``,
``Agents`` → ``agent(s)_assistant``, …), which resolve the scope
(global vs project) and the bound workspace. ``Sessions.assistant_session``
is the spawn choke point. Run ``list_assistants`` first to see valid names.
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

    Creates or reuses a shared session per (assistant, scope), named
    ``<assistant> - <scope-label>`` — e.g. ``skills_assistant - global``
    (working in ``~/.agentone/skills/``) or ``skills_assistant - MyProject``
    (the same assistant seeing the global collection plus that project's own
    items). The assistant processes the message and its response is returned
    via the auto-awaited TaskCall.

    Scope resolution (first match wins):

    1. ``project_path`` matches a registered project (by path or manifest
       dir) → that project's scope. Unmatched paths fall back to a global
       scope bound to a workspace at that path.
    2. ``context_path`` → workspace override at that path; the project
       scope is inherited from your session.
    3. Neither → your session's scope is inherited.

    Args:
        _session: The calling agent's session (bound automatically).
        name: Internal assistant name, e.g. ``project_assistant``,
            ``skills_assistant``, ``cronjobs_assistant``.
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

    cls = _class_for(assistant)
    if cls is None:
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
            # Legacy fallback: global scope bound to a workspace at the path.
            override = project_path
    else:
        project = _session.get_project()
    if context_path:
        override = context_path

    try:
        collection = cls(parent_project=project)
    except TypeError:
        collection = cls()  # top-level collections (Projects) take no parent
    project = collection.project

    if override:
        target = override.strip().rstrip("/")
        workspace = Workspaces.ensure_named(
            f"{target} assistant scope", target,
            "assistant scope override",
        )
        child = Sessions().assistant_session(
            assistant, project=project, workspace=workspace, caller=_session,
            scope_label=target.rsplit("/", 1)[-1] or "global",
        )
    else:
        child = collection.get_assistant_session(caller=_session, name=assistant)
        workspace = child.get_version_model().workspace if child is not None else None
    if child is None:
        return {"error": f"Assistant '{assistant}' could not be resolved or spawned"}
    return _send(child, assistant, task, project, workspace)


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


def _class_for(assistant: str) -> Any | None:
    """Return the collection class owning *assistant*, or *None*."""
    from runtime.agents.agents import Agents
    from runtime.cron.crons import Cronjobs
    from runtime.project.projects import Projects
    from runtime.skill.skills import Skills
    from runtime.workitems.workitems import Workitems
    from runtime.workspace.workspaces import Workspaces

    for cls in (Skills, Agents, Projects, Workspaces, Workitems, Cronjobs):
        if assistant in cls.ASSISTANT_NAMES:
            return cls
    return None


def _resolve_project(project_path: str) -> Any | None:
    """Return the registered project for *project_path*, or *None*."""
    from server.models.project import Project

    wanted = (project_path or "").strip().rstrip("/")
    if not wanted:
        return None
    project = (
        Project.objects.filter(manifest_dir=wanted).first()
        or Project.objects.filter(main_workspace__path=wanted).first()
    )
    if project is None:
        # Legacy fallback: match the resolved manifest dir (covers rows
        # created before manifest_dir existed).
        from runtime.paths import project_manifest_dir

        for candidate in Project.objects.all():
            try:
                if project_manifest_dir(candidate).as_posix().rstrip("/") == wanted:
                    project = candidate
                    break
            except Exception:  # pylint: disable=broad-exception-caught
                continue
    return project
