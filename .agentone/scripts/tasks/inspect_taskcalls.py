from __future__ import annotations

import traceback


def _wildcard_filter(value: str, field: str) -> dict:
    """Build a case-insensitive Django filter dict from a wildcard pattern.

    Patterns:
        ``foo*``   → ``__istartswith``
        ``*foo``   → ``__iendswith``
        ``*foo*``  → ``__icontains``
        ``foo``    → ``__iexact``
    """
    if value.startswith("*") and value.endswith("*"):
        return {f"{field}__icontains": value[1:-1]}
    if value.startswith("*"):
        return {f"{field}__iendswith": value[1:]}
    if value.endswith("*"):
        return {f"{field}__istartswith": value[:-1]}
    return {f"{field}__iexact": value}


def inspect_taskcalls(
    agent: str = "",
    status: str = "",
    task: str = "",
    session: str = "",
    project: str = "",
    limit: int = 50,
    prev: int | None = None,
) -> tuple[bool, dict]:
    """Query task calls with filters and cursor-based pagination.

    Text filters (``agent``, ``task``, ``session``, ``project``) support
    wildcard patterns:

    ==========  ===========
    Pattern     Behaviour
    ==========  ===========
    ``foo``     exact match (case-insensitive)
    ``foo*``    starts-with
    ``*foo``    ends-with
    ``*foo*``   contains
    ==========  ===========

    Args:
        agent:   Filter by agent name.
        status:  Filter by exact status (e.g. ``ENDED``, ``ACTIVE``, ``WAITING``, ``HALTED``).
        task:    Filter by task/function name.
        session: Filter by session PK (int) or session name.
        project: Filter by project name.
        limit:   Maximum results to return (default 50, max 500).
        prev:    Cursor — PK of the last item from the previous batch.

    Returns:
        A tuple of ``(success, result)``.
        On success, result contains:
            - status: "success"
            - calls: list of call dicts
            - next_cursor: PK of the last returned call (pass as ``prev`` for next page)
            - count: number of results
        On error, result contains:
            - status: "error"
            - message: error description
    """
    try:
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.enums.task_enums import TaskCallStatus

        limit = max(1, min(limit, 500))

        qs = AgentTaskCall.objects.select_related(
            "task_definition",
            "session",
            "session_version__agent",
            "session_version__agent__parent_project",
            "taskcall_result_run",
        ).order_by("pk")

        if agent:
            qs = qs.filter(**_wildcard_filter(agent, "session_version__agent__name"))
        if status:
            qs = qs.filter(status=status.upper())
        if task:
            qs = qs.filter(**_wildcard_filter(task, "task_definition__name"))
        if session:
            try:
                qs = qs.filter(session__pk=int(session))
            except ValueError:
                qs = qs.filter(**_wildcard_filter(session, "session__name"))
        if project:
            qs = qs.filter(
                **_wildcard_filter(project, "session_version__agent__parent_project__name")
            )
        if prev is not None:
            qs = qs.filter(pk__gt=prev)

        calls = []
        next_cursor = None
        for c in qs[:limit]:
            agent_name = (
                c.session_version.agent.name
                if c.session_version and c.session_version.agent
                else ""
            )
            task_name = (
                c.task_definition.name if c.task_definition else ""
            )
            session_name = c.session.name if c.session else ""
            project_name = (
                c.session_version.agent.parent_project.name
                if c.session_version
                and c.session_version.agent
                and c.session_version.agent.parent_project
                else ""
            )
            calls.append({
                "pk": c.pk,
                "status": c.status,
                "status_detail": c.status_detail,
                "agent": agent_name,
                "task": task_name,
                "session_pk": c.session.pk if c.session else None,
                "session": session_name,
                "project": project_name,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                f"{'partial_' if not c.ended_at else ''}result": c.get_result(allow_partial_results=True),
            })
            next_cursor = c.pk

        return (True, {
            "status": "success",
            "calls": calls,
            "next_cursor": next_cursor,
            "count": len(calls),
        })
    except Exception as e:
        return (False, {
            "status": "error",
            "message": f"inspect_taskcalls failed: {e}\n{traceback.format_exc()}",
        })
