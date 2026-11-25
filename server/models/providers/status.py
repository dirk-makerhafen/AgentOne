"""Read-only status/error summaries shared by provider UI surfaces.

The insights and settings pages need the same answer to two questions:

* is this provider/key currently blocked (health, cooldown, or a live cap)?
* how many of its last N completed queries failed, and why?

Keeping the calculation here means the templates only render a dict and never
have to make ORM decisions.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from server.models.enums.provider_enums import HealthStatus
from server.models.queries.response import ResponseStatus


def recent_query_error_stats(responses, limit: int = 100) -> dict[str, Any]:
    """Summarise the last *limit* completed responses in *responses*.

    ``ACTIVE`` / ``WAITING`` responses are excluded from both the sample and
    the denominator — an in-flight call has not failed yet.  Failures include
    provider rate limits (stored with ``error_type="rate_limit"``) so a parked
    provider is visible in the error rate rather than looking healthy.
    """
    rows = list(
        responses.filter(
            status__in=(ResponseStatus.SUCCESS, ResponseStatus.FAILURE)
        )
        .order_by("-created_at")
        .values("status", "error_type")[:limit]
    )
    failures = [row for row in rows if row["status"] == ResponseStatus.FAILURE]
    types = Counter(
        (row["error_type"] or "unknown").strip() or "unknown" for row in failures
    )
    rate_limited = types.pop("rate_limit", 0)
    return {
        "window": limit,
        "sample_size": len(rows),
        "failures": len(failures),
        "rate_limited": rate_limited,
        "error_rate": round(len(failures) * 100 / len(rows), 1) if rows else 0.0,
        # Top three non-rate-limit causes, so the card explains *why* it is
        # failing without having to open every query.
        "error_types": [
            {"type": name, "count": count} for name, count in types.most_common(3)
        ],
    }


def status_summary(
    row,
    *,
    rate_limited: bool,
    rate_limit_reason: str = "",
    active_calls: int | None = None,
    parallel_limit: int = 0,
) -> dict[str, Any]:
    """Common status fields for an :class:`ApiProvider` or :class:`ApiKey`."""
    cooldown_until = getattr(row, "rate_limit_until", None)
    label = row.get_status_display()
    if row.status == HealthStatus.RATE_LIMITED and not rate_limited:
        label = "Rate limited (cooldown elapsed)"
    return {
        "id": row.pk,
        "status": row.status,
        "status_label": label,
        "health_label": row.health_label,
        "status_reason": row.status_reason,
        "status_retry_at": row.status_retry_at,
        "cooldown_until": cooldown_until,
        "rate_limit_hits": getattr(row, "rate_limit_hits", 0),
        "consecutive_failures": row.consecutive_failures,
        "enabled": getattr(row, "enabled", True),
        "rate_limited": rate_limited,
        "rate_limit_reason": rate_limit_reason,
        "active_calls": active_calls,
        "parallel_limit": parallel_limit,
    }
