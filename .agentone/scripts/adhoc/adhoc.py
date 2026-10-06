"""Session-private ad-hoc tools — thin bound wrappers.

Ad-hoc tools are single Python functions that live only for this session.
They are NOT registered tools: the only way to run one is
``adhoc_function_call``.  Typical loop: ``adhoc_list`` to see what exists,
``adhoc_create`` once, then ``adhoc_function_call`` as often as needed.

Rules:
- Names: 3-41 chars, lowercase letter first, then lowercase/digits/_ .
- Source MUST define a top-level ``def run(params: dict) -> dict``.  It may
  also return ``(bool, dict)``.  Anything else is normalized.
- Creation is auto-allowed but scanned: dangerous code (network, ctypes,
  shell-out, cross-session paths, …) is rejected with a reason.
- Archive is a visibility state, not a freeze: tools keep working on
  archived sessions, like messages, files, and templates.
- Max 20 tools per session, 64KB source each, 60s call timeout.

All real logic lives in ``runtime/adhoc_tools.py`` so it is unit-testable
without the loader; these functions only forward the bound session.
"""

from __future__ import annotations

from typing import Dict, Optional

from runtime.session.session import Session


def adhoc_create(
    _session: Session,
    name: str,
    source: str,
    description: str = "",
    params_schema: Optional[Dict] = None,
) -> tuple[bool, dict]:
    """Create one session-private helper function for reuse this session.

    Use this when you need the same small computation in several steps and
    inlining it via ``python`` every time would be wasteful or error-prone
    (parsing, scoring, formatting, reshaping tool output).

    Do NOT use this for one-shot code — call ``python`` directly instead.
    Do NOT use this for anything that must outlive the session (work items,
    project files, manifests).

    Args:
        name: Tool name (3-41 chars, lowercase letter first).
        source: Full Python source. Must define ``def run(params: dict)``.
            Keep it dependency-free (stdlib only) and side-effect free apart
            from returning data. Do NOT print() — stdout must stay clean
            for the result envelope; return data instead. Must pass the
            safety scan — no network, no ctypes, no subprocess/shell-out,
            no cross-session paths.
        description: One line on what it does (shown by ``adhoc_list``).
        params_schema: Optional JSON-schema-subset dict, e.g.
            ``{"type": "object", "properties": {"text": {"type": "string"}},
            "required": ["text"]}``. Calls are validated against it.

    Returns:
        (True, {status, name, version}) on success, else (False, {status, message}).
    """
    from runtime import adhoc_tools as _adhoc

    try:
        return _adhoc.create_adhoc_tool(_session, name, source, description, params_schema)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        import traceback

        return (False, {"status": "exception", "message": f"{exc}\n{traceback.format_exc()}"})


def adhoc_list(_session: Session) -> tuple[bool, dict]:
    """List this session's ad-hoc tools (metadata only, no source).

    Call this before ``adhoc_function_call`` when you are unsure what exists.
    Returns (True, {status, tools: [{name, description, version, updated_at}]}).
    """
    from runtime import adhoc_tools as _adhoc

    try:
        return _adhoc.list_adhoc_tools(_session)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        import traceback

        return (False, {"status": "exception", "message": f"{exc}\n{traceback.format_exc()}"})


def adhoc_read(_session: Session, name: str) -> tuple[bool, dict]:
    """Read one ad-hoc tool's source plus metadata (for debug/iterate).

    Args:
        name: Tool name from ``adhoc_list``.

    Returns:
        (True, {status, name, source, meta}) or (False, {status, message}).
    """
    from runtime import adhoc_tools as _adhoc

    try:
        return _adhoc.read_adhoc_tool(_session, name)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        import traceback

        return (False, {"status": "exception", "message": f"{exc}\n{traceback.format_exc()}"})


def adhoc_update(
    _session: Session,
    name: str,
    source: str | None = None,
    description: str | None = None,
    params_schema: Optional[Dict] = None,
) -> tuple[bool, dict]:
    """Update one ad-hoc tool's source and/or metadata (bumps version).

    Args:
        name: Existing tool name.
        source: New full Python source (re-scanned; must still define ``run``).
            Omit to keep the current source.
        description: New description. Omit to keep.
        params_schema: New schema (replaces). Omit to keep; there is no
            null-vs-omit distinction at the tool layer — to drop a schema,
            delete and re-create the tool.

    Returns:
        (True, {status, name, version}) or (False, {status, message}).
    """
    from runtime import adhoc_tools as _adhoc

    try:
        return _adhoc.update_adhoc_tool(_session, name, source, description, params_schema)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        import traceback

        return (False, {"status": "exception", "message": f"{exc}\n{traceback.format_exc()}"})


def adhoc_delete(_session: Session, name: str) -> tuple[bool, dict]:
    """Delete one session ad-hoc tool.

    Args:
        name: Tool name from ``adhoc_list``.

    Returns:
        (True, {status, name}) or (False, {status, message}).
    """
    from runtime import adhoc_tools as _adhoc

    try:
        return _adhoc.delete_adhoc_tool(_session, name)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        import traceback

        return (False, {"status": "exception", "message": f"{exc}\n{traceback.format_exc()}"})


def adhoc_function_call(_session: Session, name: str, params: Optional[Dict] = None) -> tuple[bool, dict]:
    """Run one session ad-hoc tool by name — the ONLY way to execute it.

    Tools must be created via ``adhoc_create`` first; listing via
    ``adhoc_list`` shows what exists. The tool source is re-scanned on
    every call, so edits made behind the wrapper's back cannot sneak
    past the guardrail. ``params`` are validated against the tool's
    stored schema (if any) and absolute-looking path strings are checked
    against the workspace policy.

    Execution is an isolated subprocess (60s timeout, truncated output), so
    a crashing helper cannot harm the session.

    Args:
        name: Tool name from ``adhoc_list``.
        params: JSON object passed as ``run(params)``. Defaults to {}.

    Returns:
        The helper's result merged into {status, return_code, ...}, or
        (False, {status: error, message/stderr, ...}) when blocked/failed.
    """
    from runtime import adhoc_tools as _adhoc

    try:
        return _adhoc.call_adhoc_tool(_session, name, params)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        import traceback

        return (False, {"status": "exception", "message": f"{exc}\n{traceback.format_exc()}"})
