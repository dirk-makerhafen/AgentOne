"""API Key model — per-key rate limits and usage tracking."""
from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from server.models.base_model import BaseModel
from server.models.queries.response import Response


# Cooldown defaults (seconds) for provider rate-limits (429/503) that carry
# no explicit retry delay.
DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 60
"""Sane default when a 429/503 arrives without a retry delay (dosage 429s)."""

QUOTA_EXHAUSTED_COOLDOWN_SECONDS = 3600
"""Long default when the limit reads like quota exhaustion (no retry will help
until the window resets — e.g. OpenCode Zen's daily quota)."""

MAX_COOLDOWN_SECONDS = 3600  
"""Ceiling for the escalating backoff (1 hour)."""

QUOTA_REASON_PATTERNS = ("quota", "insufficient", "resource exhausted", "daily limit", "exceeded your daily")



class ApiKey(BaseModel):
    """An API key for a provider, with independent rate-limit tracking."""

    api_provider = models.ForeignKey("server.ApiProvider", on_delete=models.CASCADE, related_name="api_keys")
    comment = models.CharField(max_length=512, default="", null=True)
    key = models.CharField(max_length=512)
    enabled = models.BooleanField(default=True)

    # 0 = unlimited
    limit_request_per_day = models.IntegerField(default=0)
    limit_request_per_minute = models.IntegerField(default=0)
    limit_tokens_per_day = models.IntegerField(default=0)
    limit_tokens_per_minute = models.IntegerField(default=0)

    # Provider-imposed cooldown.  When a provider returns a 429 with a retry
    # delay (e.g. Google's ``RetryInfo.retryDelay``), the end of the wait is
    # stored here so the rate limiter skips this key until then instead of
    # hammering it.  ``None`` means no active cooldown.
    rate_limit_until = models.DateTimeField(default=None, null=True, blank=True)

    # Consecutive 429 hits since the last success (or cooldown reset).  Drives
    # escalating backoff: each new 429 after an ``rate_limit_until`` that has
    # already passed (re-slammed while still throttling) multiplies the wait.
    rate_limit_hits = models.IntegerField(default=0)

    @property
    def total_llm_queries(self) -> int:
        """Total number of queries made through this API key."""
        return self.related_queries.count()

    @property
    def total_prompt_tokens(self) -> int:
        """Total prompt tokens consumed across all responses for this key."""
        result = Response.objects.filter(query__apikey=self).aggregate(
            total=Sum("prompt_tokens")
        )["total"]
        return result or 0

    @property
    def total_completion_tokens(self) -> int:
        """Total completion tokens consumed across all responses for this key."""
        result = Response.objects.filter(query__apikey=self).aggregate(
            total=Sum("completion_tokens")
        )["total"]
        return result or 0

    @property
    def queries(self):
        """Return the related Query queryset for this API key."""
        return self.related_queries  # pyright: ignore[reportAttributeAccessIssue]

    def record_provider_cooldown(self, retry_after_seconds: float | None, *, reason: str = "") -> float:
        """Park this key until the provider's requested cooldown passes.

        Called when the provider returns a rate-limit or transient
        unavailability error — HTTP 429 (e.g. Google's ``RetryInfo.retryDelay``
        or a ``Retry-After`` header) or HTTP 503 ("high demand, try again
        later").  The rate limiter then skips this key (``is_rate_limited``
        returns True) until ``rate_limit_until``, so the scheduler doesn't
        re-slam it.

        Backoff is escalating: each consecutive 429/503 (no intervening
        success) doubles the wait, capped at :data:`MAX_COOLDOWN_SECONDS`.
        When the error carries no explicit delay, the default is long if the
        reason reads like quota exhaustion
        (``QUOTA_EXHAUSTED_COOLDOWN_SECONDS``) and short otherwise
        (``DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS``).

        Returns the cooldown, in seconds.
        """
        from datetime import timedelta

        hits = (self.rate_limit_hits or 0) + 1
        base = retry_after_seconds
        if not base or base <= 0:
            base = (
                QUOTA_EXHAUSTED_COOLDOWN_SECONDS
                if self._looks_like_quota(reason)
                else DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS
            )
        # level is 0-based; 4+ consecutive hits stop growing (8x ceiling).
        level = min(hits - 1, 3)
        cooldown = min(base * (2 ** level), MAX_COOLDOWN_SECONDS)
        ApiKey.objects.filter(pk=self.pk).update(
            rate_limit_until=timezone.now() + timedelta(seconds=cooldown),
            rate_limit_hits=hits,
        )
        self.rate_limit_until = timezone.now() + timedelta(seconds=cooldown)
        self.rate_limit_hits = hits
        return cooldown

    def clear_provider_cooldown(self) -> None:
        """Clear any active provider cooldown (e.g. after a successful call).

        Also resets the consecutive-hit counter so the next 429 starts from
        the base cooldown again.
        """
        if self.rate_limit_until or self.rate_limit_hits:
            ApiKey.objects.filter(pk=self.pk).update(
                rate_limit_until=None, rate_limit_hits=0
            )
            self.rate_limit_until = None
            self.rate_limit_hits = 0

    def requests_last_minute(self) -> int:
        """Number of successful responses in the last 60 seconds for this key."""
        since = timezone.now() - timedelta(seconds=60)
        return Response.objects.filter(
            query__apikey=self, status="SUCCESS", created_at__gte=since
        ).count()

    def requests_last_hour(self) -> int:
        """Number of successful responses in the last 60 minutes for this key."""
        since = timezone.now() - timedelta(minutes=60)
        return Response.objects.filter(
            query__apikey=self, status="SUCCESS", created_at__gte=since
        ).count()

    def requests_today(self) -> int:
        """Number of successful responses since midnight today for this key."""
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return Response.objects.filter(
            query__apikey=self, status="SUCCESS", created_at__gte=today
        ).count()

    def tokens_last_minute(self) -> int:
        """Total tokens (prompt + completion) in last 60 seconds for this key."""
        since = timezone.now() - timedelta(seconds=60)
        result = Response.objects.filter(
            query__apikey=self, status="SUCCESS", created_at__gte=since
        ).aggregate(total=Sum("prompt_tokens") + Sum("completion_tokens"))
        return result["total"] or 0

    def tokens_last_hour(self) -> int:
        """Total tokens (prompt + completion) in the last 60 minutes for this key."""
        since = timezone.now() - timedelta(minutes=60)
        result = Response.objects.filter(
            query__apikey=self, status="SUCCESS", created_at__gte=since
        ).aggregate(total=Sum("prompt_tokens") + Sum("completion_tokens"))
        return result["total"] or 0

    def tokens_today(self) -> int:
        """Total tokens (prompt + completion) since midnight today for this key."""
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = Response.objects.filter(
            query__apikey=self, status="SUCCESS", created_at__gte=today
        ).aggregate(total=Sum("prompt_tokens") + Sum("completion_tokens"))
        return result["total"] or 0

    def active_call_count(self) -> int:
        """Number of LLM queries currently ACTIVE using this specific key."""
        from server.models.queries.query import Query

        return Query.objects.filter(apikey=self, status="ACTIVE").count()

    def is_rate_limited(self) -> tuple[bool, str]:
        """Check all key-level limits.

        Returns:
            A tuple ``(is_limited, reason)`` where ``reason`` is empty when not limited.
        """
        if not self.enabled:
            return True, "disabled"

        if self.rate_limit_until and timezone.now() < self.rate_limit_until:
            return True, f"cooldown_until:{self.rate_limit_until.isoformat()}"

        if self.limit_request_per_minute > 0:
            rpm = self.requests_last_minute()
            if rpm >= self.limit_request_per_minute:
                return True, f"rpm:{rpm}/{self.limit_request_per_minute}"

        if self.limit_request_per_day > 0:
            rpd = self.requests_today()
            if rpd >= self.limit_request_per_day:
                return True, f"rpd:{rpd}/{self.limit_request_per_day}"

        if self.limit_tokens_per_minute > 0:
            tpm = self.tokens_last_minute()
            if tpm >= self.limit_tokens_per_minute:
                return True, f"tpm:{tpm}/{self.limit_tokens_per_minute}"

        if self.limit_tokens_per_day > 0:
            tpd = self.tokens_today()
            if tpd >= self.limit_tokens_per_day:
                return True, f"tpd:{tpd}/{self.limit_tokens_per_day}"

        return False, ""

    def pending_calls(self):
        """All AgentTaskCalls waiting due to this key's rate limits, FIFO order.

        Note: calls waiting on the model limit show up in ``AiModel.pending_calls()``.
        """
        from server.models.tasks.agent_task_call import (AgentTaskCall, pending_rate_limit_call_ids)
        return AgentTaskCall.objects.filter(pk__in=pending_rate_limit_call_ids(provider_id=self.api_provider_id)).order_by("created_at")

    def _looks_like_quota(self, reason: str) -> bool:
        """Best-effort detection of quota exhaustion from a 429 message."""
        message = (reason or "").lower()
        return any(pattern in message for pattern in QUOTA_REASON_PATTERNS)

    def __str__(self) -> str:
        return f"ApiKey:{self.comment or self.pk} ({self.api_provider})"
