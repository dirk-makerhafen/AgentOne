"""
Reports a tool call that could not be executed because its arguments were invalid.

This task replaces a tool call the LLM produced with a missing / unknown tool
or arguments that fail the tool's declared JSON schema.  It never executes the
original tool — it just returns a clear error so the agent can correct the
call and retry.
"""

from __future__ import annotations

import json
from typing import Any

from runtime.session.session import Session


def catch_tool_argument_error(
    _session: Session,
    tool_name: str,
    arguments: Any,
    error: str = "",
) -> tuple[bool, dict[str, Any]]:
    """Return an error describing a rejected tool call.

    Args:
        _session: The active agent session (unused).
        tool_name: The name of the tool that was originally called.
        arguments: The (invalid) arguments the LLM supplied.
        error:     A short description of the validation failure.

    Returns:
        ``(False, {"status": "error", "message": ...})``.
    """
    try:
        args_repr = json.dumps(arguments, default=str)
    except (TypeError, ValueError):
        args_repr = repr(arguments)

    message = (
        f"Tool '{tool_name}' was NOT executed because its arguments failed "
        f"validation.\n"
        f"Reason: {error or 'unknown validation failure'}\n"
        f"Arguments received: {args_repr}\n"
        f"Check the tool's documented parameters and re-issue the call with "
        f"correct argument if needed."
    )
    return False, {"status": "error", "message": message}
