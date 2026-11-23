"""Shared, path-aware reporting for manifest loading failures.

A reload loads many independent files. An error that only says ``KeyError:
'function'`` (or names just a directory) forces the reader to guess which
manifest and which entry failed. Every helper here keeps the file path and
the offending entry in the message, and logs the full traceback for the
cases where a loader deliberately skips a bad file and carries on.
"""

# pylint: disable=too-many-arguments
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)


def describe_exception(exc: BaseException) -> str:
    """Return ``ExceptionType: message`` without losing an empty message."""
    detail = str(exc).strip()
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


def entry_label(entry: str | Mapping[str, Any] | None) -> str:
    """Human-readable label for a manifest entry or list index."""
    if entry is None:
        return ""
    if isinstance(entry, str):
        return entry
    name = entry.get("name")
    return str(name) if name else ""


def format_load_error(
    context: str,
    *,
    path: Path | str | None = None,
    entry: str | Mapping[str, Any] | None = None,
    exc: BaseException | None = None,
    detail: str | None = None,
) -> str:
    """Format a load error with the file and entry that caused it.

    Examples::

        agent.md (/repo/.agentone/agents/foo/agent.md): ValueError: ...
        scripts.md entry (/repo/.agentone/scripts/scripts.md) commands[2] 'deploy':
            ValueError: missing execution key ...
    """
    location = str(path) if path is not None else "unknown file"
    message = f"{context} ({location})"
    label = entry_label(entry)
    if label:
        message += f" {label}"
    reason = describe_exception(exc) if exc is not None else detail
    if reason:
        message += f": {reason}"
    return message


def load_error(
    context: str,
    *,
    path: Path | str | None = None,
    entry: str | Mapping[str, Any] | None = None,
    exc: BaseException | None = None,
    detail: str | None = None,
    exception_type: type[Exception] = RuntimeError,
) -> Exception:
    """Build an exception whose message identifies the failing manifest.

    ``exception_type`` keeps an existing, caller-visible exception contract
    (e.g. ``ValueError`` for a rejected manifest field).
    """
    return exception_type(format_load_error(context, path=path, entry=entry, exc=exc, detail=detail))


def record_load_issue(
    details: list | None,
    context: str,
    *,
    path: Path | str | None = None,
    entry: str | Mapping[str, Any] | None = None,
    exc: BaseException | None = None,
    detail: str | None = None,
    type_: str = "script",
) -> str:
    """Record a non-fatal load failure and log its traceback.

    Uses the same ``details`` shape as the other loaders, with ``action:
    "error"`` so ``run_reload_all`` surfaces it in ``errors`` / the summary
    instead of silently dropping the file.
    """
    message = format_load_error(context, path=path, entry=entry, exc=exc, detail=detail)
    logger.warning("%s", message, exc_info=exc is not None)
    if details is not None:
        details.append({
            "name": entry_label(entry) or (Path(path).name if path is not None else context),
            "type": type_,
            "action": "error",
            "path": str(path) if path is not None else "",
            "error": message,
        })
    return message
