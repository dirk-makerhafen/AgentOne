"""Cron schedule parsing shared by the model, loaders and executor.

Keeping this in one place means every write path (model ``save()``, manifest
loader, API/assistant helpers and :func:`execute_cron_job`) expands the same
human-friendly shorthands and rejects the same invalid expressions.
"""
from __future__ import annotations

import re
from datetime import datetime

from croniter import croniter
from django.utils import timezone

_EVERY_RE = re.compile(
    r"^every\s+(\d+)\s*(min|m|minute|minutes|hour|hours|h)\s*$"
)


def expand_shorthand(schedule: str) -> str:
    """Convert human-friendly shorthands to cron expressions.

    Supported:
      ``every N (min|m|minute|minutes)``  →  ``*/N * * * *``
      ``every N (hour|hours|h)``          →  ``0 */N * * *``

    Anything else is returned unchanged (standard cron, ``@daily``, …).
    """
    s = (schedule or "").strip().lower()
    match = _EVERY_RE.match(s)
    if not match:
        return schedule
    n = int(match.group(1))
    unit = match.group(2)
    if unit in ("min", "m", "minute", "minutes"):
        return f"*/{n} * * * *"
    return f"0 */{n} * * *"


def compute_next_run(schedule: str) -> datetime | None:
    """Return the next run datetime for *schedule*, or ``None`` if invalid.

    Supports standard cron (``*/5 * * * *``), shorthands (``@daily``,
    ``@hourly``), and human-friendly ``every N (min|m|hour|h)``.
    """
    try:
        expanded = expand_shorthand(schedule)
        return croniter(expanded, timezone.localtime()).get_next(datetime)
    except (ValueError, KeyError, TypeError, ZeroDivisionError):
        return None
