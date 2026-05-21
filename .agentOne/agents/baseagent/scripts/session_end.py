"""
End a subagent session (mark as inactive).
"""


def session_end(session, session_pk):
    """
    Mark a child session as inactive, preventing further processing.

    Args:
        session: The calling agent's session (bound automatically).
        session_pk: The pk of the child session to end.

    Returns:
        A dict with result or error.
    """
    from server.models.sessions.session import SessionModel
    try:
        child_session_model = SessionModel.objects.get(pk=session_pk)
    except SessionModel.DoesNotExist:
        return {"error": f"Session {session_pk} not found"}

    child_session_model.is_active = False
    child_session_model.save()
    return {"result": f"Session {session_pk} ended"}
