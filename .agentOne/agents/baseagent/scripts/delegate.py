"""
Delegate a task to a subagent.

Single-turn: creates one child session per parent session, returns result.
Multi-turn: creates a dedicated child session, returns session_pk for follow-up.
Background: same as multi-turn but returns immediately.
"""

from time import time
from runtime.agents.session import Session


def delegate(session, subagent_name, query, session_pk=None):
    """
    Delegate a task to a named subagent.

    When session_pk is given, resumes that existing child session (multi-turn).
    Otherwise creates a new child session based on the subagent's configured lifecycle.

    Args:
        session: The calling agent's session (bound automatically).
        subagent_name: Name of the subagent to delegate to.
        query: The task description or message to send.
        session_pk: Optional pk of an existing child session to continue (multi-turn).

    Returns:
        A dict with keys:
          - result: the final output from the subagent (single-turn) or "delegated"
          - session_pk: the child session pk for follow-up
          - error: if something went wrong
    """
    av = session.agent.get_version_model()
    subagent_version = av.subagent_versions.filter(agent__name=subagent_name).first()
    if not subagent_version:
        return {"error": f"Subagent '{subagent_name}' not found"}

    config = av.subagent_configs.get(subagent_name, {})
    lifecycle = config.get("lifecycle", "single")
    parent_sv = session.get_version_model()

    if session_pk:
        from server.models.sessions.session import SessionModel
        try:
            child_session_model = SessionModel.objects.get(pk=session_pk)
        except SessionModel.DoesNotExist:
            return {"error": f"Session {session_pk} not found"}
        child_session = Session(session_model=child_session_model)
    else:
        if lifecycle == "single":
            name = f"p{parent_sv.session.pk}:{subagent_name}"
        else:
            name = f"p{parent_sv.session.pk}:{subagent_name}:{int(time())}"
        child_sv = subagent_version.get_or_create_session(
            name=name,
            workingdir=parent_sv.workingdir,
            parent_instance_version=parent_sv,
        )
        child_session = Session(session_model=child_sv.session, pinned_session_version=child_sv)

    parts = [{"type": "message", "content_type": "text", "content": query}]
    taskcall = child_session.add_user_message(parts=parts)

    if lifecycle == "single" or lifecycle == "background":
        # taskcall will be automatically resolved to its result by the backend
        return {"result": taskcall , "session_pk": child_session.model.pk}

    return {"result": "delegated", "session_pk": child_session.model.pk}
