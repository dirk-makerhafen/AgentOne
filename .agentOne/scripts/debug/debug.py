"""
Debug/test command for development.
Supports sub-commands via the 'type' parameter:

- approval: Tests the guardrail/approval flow (command requires approval)
- ping: Simple liveness check
"""

from __future__ import annotations

from runtime.session.session import Session


def debug(session: Session, type: str = "ping") -> str:
    """
    Debug command for testing various system features.

    Args:
        session: The active agent session.
        type: Sub-command type - "ping" (default) or "approval".

    Returns:
        A status message.
    """
    if type == "approval":
        return "Approval test passed."
    elif type == "ping":
        return "pong"
    else:
        return f"Unknown debug type: {type}"
