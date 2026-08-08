"""
Reports a tool call that was denied by the user at the approval gate.

Runs in place of a tool call whose approval was required but declined.  It
never executes the original tool — it just returns a clear message (including
any reason and user feedback) so the agent understands the denial and can
adjust its approach.
"""

from __future__ import annotations

from typing import Any

from runtime.session.session import Session


def catch_approval_denied(
    _session: Session,
    tool_name: str,
    reason: str = "",
    feedback: str = "",
) -> tuple[bool, dict[str, Any]]:
    """Return an error describing a denied tool call.

    Args:
        _session: The active agent session (unused).
        tool_name: The name of the tool whose approval was denied.
        reason:   The approval/guardrail reason (may be empty).
        feedback: Optional comment the user left when denying.

    Returns:
        ``(False, {"status": "error", "message": ...})``.
    """
    lines = [
        f"Tool '{tool_name}' was NOT executed because the required approval "
        "was DENIED by the user."
    ]
    if reason:
        lines.append(f"Reason: {reason}")
    if feedback:
        lines.append(f"User feedback: {feedback}")
    lines.append(
        "Adjust your approach accordingly, or re-issue the call with "
        "different parameters if appropriate."
    )
    return False, {"status": "error", "message": "\n".join(lines)}
