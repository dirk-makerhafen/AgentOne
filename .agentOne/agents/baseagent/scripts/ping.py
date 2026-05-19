"""
Simple liveness check command. Responds with agent/session info.
"""

from runtime.agents.session import Session


def ping(session: Session, message: str | None = None):
    """
    Return a pong string with agent name, version, and session info.

    Args:
        session: The active agent session.
        message: Optional message to echo back.

    Returns:
        A greeting string.
    """
    r = (
        f"Pong from Agent {session.agent.name}, "
        f"Version {session.agent.version_number}, "
        f"Session {session.name}"
    )
    if message:
        r += f"\nMessage received:{message}"
    return r
