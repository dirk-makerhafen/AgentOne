"""Decide whether a failure should wait, fail over, or surface.

The important distinction is **not** "429 → switch".  A short minute-window
limit is often worth waiting for, while daily quota exhaustion, a revoked key
or a missing model id will not recover by waiting.  The decision combines the
provider's own hint (``Retry-After`` / ``RetryInfo``), the failure scope and
the session's workload tolerance (chat / background / test).
"""
from __future__ import annotations

from dataclasses import dataclass

from runtime.routing.intent import FAILOVER_NONE, RouteIntent

ACTION_WAIT = "wait"
ACTION_FAILOVER = "failover"
ACTION_RAISE = "raise"

#: Cooldown guesses when the provider gives no hint.
DEFAULT_TRANSIENT_WAIT = 60.0
DEFAULT_QUOTA_WAIT = 3600.0

_QUOTA_HINTS = (
    "quota",
    "insufficient",
    "resource exhausted",
    "daily limit",
    "exceeded your daily",
    "per day",
    "billing",
)


@dataclass(frozen=True)
class ErrorDecision:
    """What the caller should do after one failed attempt."""

    action: str
    reason: str
    wait_seconds: float = 0.0

    @property
    def should_wait(self) -> bool:
        return self.action == ACTION_WAIT

    @property
    def should_failover(self) -> bool:
        return self.action == ACTION_FAILOVER


def _looks_like_quota(message: str) -> bool:
    lower = (message or "").lower()
    return any(hint in lower for hint in _QUOTA_HINTS)


def _has_failover(intent: RouteIntent) -> bool:
    return intent.failover != FAILOVER_NONE


def decide_failure(
    info,
    *,
    intent: RouteIntent,
) -> ErrorDecision:
    """Classify one provider failure into wait / failover / raise."""
    kind = getattr(info, "kind", "unknown")
    message = getattr(info, "message", "") or ""
    retry_after = getattr(info, "retry_after", None)
    scope = getattr(info, "scope", "request")
    budget = intent.wait_seconds

    if kind == "bad_request" and not getattr(info, "config_like", False):
        # Context-length / malformed-prompt failures are request problems.
        # Switching providers just burns quota on the same bad request.
        return ErrorDecision(ACTION_RAISE, "request_error")

    if kind == "rate_limit":
        wait = float(retry_after or 0)
        if wait <= 0:
            wait = DEFAULT_QUOTA_WAIT if _looks_like_quota(message) else DEFAULT_TRANSIENT_WAIT
        if budget <= 0:
            return ErrorDecision(ACTION_RAISE, "rate_limit_no_wait")
        if wait <= budget:
            return ErrorDecision(ACTION_WAIT, "rate_limit_within_budget", wait)
        if _has_failover(intent):
            return ErrorDecision(ACTION_FAILOVER, "rate_limit_exceeds_budget")
        return ErrorDecision(ACTION_WAIT, "rate_limit_wait_only", wait)

    if kind in ("model_not_found", "auth") or getattr(info, "config_like", False):
        # Sticky failures: waiting cannot help.
        if _has_failover(intent):
            return ErrorDecision(ACTION_FAILOVER, f"{kind}_sticky")
        return ErrorDecision(ACTION_RAISE, f"{kind}_no_failover")

    if kind in ("timeout", "server", "connection"):
        # Transient transport/provider trouble.  For interactive chats a
        # sibling is usually better than a spinner; for background work a
        # short wait is fine when there is nothing to fail over to.
        if _has_failover(intent):
            return ErrorDecision(ACTION_FAILOVER, f"{kind}_transient")
        if budget > 0:
            wait = float(retry_after or DEFAULT_TRANSIENT_WAIT)
            return ErrorDecision(ACTION_WAIT, f"{kind}_wait", min(wait, float(budget)))
        return ErrorDecision(ACTION_RAISE, f"{kind}_no_wait")

    if _has_failover(intent):
        return ErrorDecision(ACTION_FAILOVER, f"{scope}:{kind}")
    return ErrorDecision(ACTION_RAISE, f"{scope}:{kind}:no_failover")


def decide_admission(exc, *, intent: RouteIntent) -> ErrorDecision:
    """Decide what to do when :class:`RateLimitChecker` refuses a candidate.

    ``RateLimitError`` with ``wait=True`` means the checker deliberately chose
    to wait for the current key/provider (short cooldown inside the budget).
    Anything else means this candidate has no capacity right now.
    """
    if getattr(exc, "wait", False):
        return ErrorDecision(ACTION_WAIT, "admission_wait")
    if intent.failover == FAILOVER_NONE:
        if intent.wait_seconds <= 0:
            return ErrorDecision(ACTION_RAISE, "admission_no_failover_no_wait")
        return ErrorDecision(ACTION_WAIT, "admission_wait_only")
    return ErrorDecision(ACTION_FAILOVER, "admission_failover")
