"""Failure detail for LLM queries.

``Query`` only stores a terminal ``status``; the human-readable reason lives on
the newest ``Response`` (``error_type`` / ``error_message``).  A terminal query
card is immutable in the UI, so the reason must be persisted *before* the query
status flips — otherwise the browser caches a bare ``FAILURE`` pill forever.

Older rows can predate those fields; for them the last ``DebugLogEntry`` with
an exception is used as a read-only fallback.  Nothing here writes on read.
"""
from __future__ import annotations

import re
from typing import Any

_GENERIC_KINDS = {"unknown", "exception", "error", "failure", "failed"}
_SUMMARY_LIMIT = 64
_TOOLTIP_LIMIT = 160


def _text(value: Any) -> str:
    return str(value or "").strip()


def _one_line(value: Any) -> str:
    return " ".join(_text(value).split())


def _shorten(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _last_traceback_line(traceback_text: str) -> str:
    """The final traceback line is ``ExceptionType: message`` — best short reason."""
    lines = [line.strip() for line in traceback_text.splitlines() if line.strip()]
    if not lines:
        return ""
    # Drop the module path on qualified exception names for readability.
    line = re.sub(
        r"^(?:[A-Za-z_]\w*\.)+([A-Za-z_]\w*(?:Error|Exception)):", r"\1:", lines[-1]
    )
    return _shorten(line, 500)


def query_failure(query, response=None) -> dict[str, str]:
    """Return read-only failure detail for *query* (safe to call while rendering).

    Keys: ``type``, ``message``, ``traceback``, ``summary`` (short inline reason)
    and ``tooltip`` (full one-line reason for the collapsed card).
    """
    result = {"type": "", "message": "", "traceback": "", "summary": "", "tooltip": ""}
    from server.models.queries.query import QueryStatus

    if query.status not in (QueryStatus.FAILURE, QueryStatus.RATE_LIMITED):
        return result

    if response is None:
        response = query.related_response.order_by("-pk").first()
    if response is not None:
        result["type"] = _one_line(response.error_type)
        result["message"] = _text(response.error_message)

    if not result["message"]:
        from server.models.debug_log_entry import DebugLogEntry

        entry = (
            DebugLogEntry.objects.filter(
                session_id=query.session_id,
                event="exception",
                created_at__gte=query.created_at,
            )
            .order_by("-pk")
            .first()
        )
        if entry is not None:
            payload = entry.data if isinstance(entry.data, dict) else {}
            raw = _text(payload.get("exception"))
            result["traceback"] = raw
            result["message"] = _last_traceback_line(raw)
            if not result["type"]:
                result["type"] = "exception"

    if not result["type"] and not result["message"]:
        return result

    kind = result["type"]
    message = _one_line(result["message"])
    first_line = _shorten(message, _SUMMARY_LIMIT)
    if kind and kind.lower() not in _GENERIC_KINDS:
        summary = f"{kind}: {first_line}" if first_line else kind
    else:
        summary = first_line or kind
    result["summary"] = _shorten(summary, _SUMMARY_LIMIT)
    tooltip = (
        f"{kind}: {message}"
        if kind and message and kind.lower() not in _GENERIC_KINDS
        else message or kind
    )
    result["tooltip"] = _shorten(tooltip, _TOOLTIP_LIMIT)
    return result


def record_query_failure(
    query,
    error_type: str,
    error_message: str,
    *,
    status=None,
    expect: dict[str, Any] | None = None,
) -> int:
    """Persist the reason on a Response, then flip the Query to a terminal state.

    Returns the number of Query rows updated (0 when ``expect`` did not match).
    Existing error detail is kept, so a classified provider error is never
    replaced by a later generic wrapper exception.
    """
    from server.models.queries.query import QueryStatus
    from server.models.queries.response import Response, ResponseStatus

    status = status or QueryStatus.FAILURE
    response = query.related_response.order_by("-pk").first()
    if response is not None and response.status == ResponseStatus.SUCCESS:
        # A successful retry must not be rewritten as a failure.
        response = None

    fields = {
        "status": ResponseStatus.FAILURE,
        "error_type": _shorten(_one_line(error_type) or "failure", 64),
        "error_message": _shorten(_text(error_message) or "No error detail was recorded.", 50000),
    }
    if response is None:
        Response.objects.create(
            query=query,
            session=query.session,
            session_version=query.session_version,
            **fields,
        )
    else:
        missing = {name: value for name, value in fields.items() if not getattr(response, name, None)}
        if missing:
            response.atomic_update(**missing)
    return query.atomic_update(expect=expect, status=status)
