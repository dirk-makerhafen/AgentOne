"""
Simple liveness check command. Responds with agent/session info.
"""

from __future__ import annotations

from runtime.session.session import Session


def ping(_session: Session, message: str | None = None) -> str:
    """
    Return a pong string with agent name, version, and session info.

    Args:
        _session: The active agent session.
        message: Optional message to echo back.

    Returns:
        A greeting string.
    """
    r = (
        f"Pong from Agent {_session.agent.name}, "
        f"Version {_session.agent.version_number}, "
        f"Session {_session.name}"
    )
    if message:
        r += f"\nMessage received:{message}"
    return r
