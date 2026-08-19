from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from server.models.providers.api_key import ApiKey
    from server.models.providers.ai_model import AiModel


class RateLimitError(Exception):
    """
    Raised by RateLimitChecker.check() when no capacity is available.
    Caught separately in AgentTaskRun.apply() — does NOT trigger retry logic.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Rate limited: {reason}")


@dataclass
class RateLimitResult:
    """Returned when capacity IS available."""

    selected_key: "ApiKey | None"


@dataclass(frozen=True)
class KeyFailoverPolicy:
    """Session-level API-key rotation policy (see settings auto_failover_keys /
    max_rate_limit_wait_seconds)."""

    auto_failover: bool
    max_wait_seconds: int

    def switch_now(self, remaining_wait: float) -> bool:
        """Whether the current cooling key may be bypassed right now."""
        if self.auto_failover:
            return True
        if self.max_wait_seconds and self.max_wait_seconds > 0:
            return bool(remaining_wait) and remaining_wait > self.max_wait_seconds
        return False


class RateLimitChecker:
    """
    Called inside _execute_query, right before the API call is made.
    Only LLM-executing tasks ever call this — pure Python tasks are unaffected.

    Check order (fail-fast):
      1. Provider parallel limit
      2. Model parallel limit + model RPM/RPD/TPM/TPD
      3. Key selection — find least-loaded available key

    Raises RateLimitError if no capacity is available.
    Returns RateLimitResult with the selected key if capacity exists.
    """

    @staticmethod
    def check(aimodel: "AiModel", session=None) -> RateLimitResult:
        """Check all rate-limit tiers and return the best available API key.

        When a runtime ``Session`` is supplied, key selection honours that
        session's key-stickiness policy: by default a cooling key is *waited
        on* (no rotation to a sibling key of the same provider); auto-failover
        or an exceeded max-wait rotates to the next ready key instead.
        """
        # 1. Provider parallel limit
        limited, reason = aimodel.api_provider.is_rate_limited()
        if limited:
            raise RateLimitError(f"provider:{reason}")

        # 2. Model-level limits
        limited, reason = aimodel.is_rate_limited()
        if limited:
            raise RateLimitError(f"model:{reason}")

        # 3. Key selection — skip if provider has no keys (keyless API)
        if not aimodel.api_provider.api_keys.exists():
            return RateLimitResult(selected_key=None)

        if session is not None:
            return RateLimitChecker._session_check(aimodel, session)

        key = RateLimitChecker._select_key(aimodel)
        if key is None:
            raise RateLimitError("no_key_available: all keys are rate-limited or disabled")
        return RateLimitResult(selected_key=key)

    @staticmethod
    def _key_wait_seconds(key: "ApiKey") -> float:
        """Remaining cooldown on *key*, in seconds (0 when not cooling)."""
        if not key.rate_limit_until:
            return 0.0
        return max(0.0, (key.rate_limit_until - timezone.now()).total_seconds())

    @staticmethod
    def _session_check(aimodel: "AiModel", session) -> RateLimitResult:
        """Key selection honouring the session's key-stickiness policy.

        The session sticks to a single key per provider.  If that key is
        cooling and the policy forbids rotation (default), the call is parked
        so it waits for *that* key to recover.  With auto-failover enabled or
        the remaining wait exceeding ``max_rate_limit_wait_seconds``, the next
        ready key of the same provider is selected and adopted.
        """
        current = session.current_provider_api_key(aimodel)

        if current is not None:
            limited, reason = current.is_rate_limited()
            if not limited:
                return RateLimitResult(selected_key=current)
            # Current key is cooling — decide whether we may rotate.
            if session.key_failover_policy().switch_now(
                RateLimitChecker._key_wait_seconds(current)
            ):
                key = RateLimitChecker._select_key(aimodel, exclude=current)
                if key is not None:
                    session.set_preferred_api_key(key)
                    return RateLimitResult(selected_key=key)
                # Every other key is busy too — park until one recovers.
                raise RateLimitError(f"provider_keys:{reason}")
            raise RateLimitError(f"key:{reason}")

        key = RateLimitChecker._select_key(aimodel)
        if key is None:
            raise RateLimitError("no_key_available: all keys are rate-limited or disabled")
        # No stickiness mandate for a fresh provider — adopt the best key.
        session.set_preferred_api_key(key)
        return RateLimitResult(selected_key=key)

    @staticmethod
    def _select_key(aimodel: "AiModel", exclude: "ApiKey | None" = None) -> "ApiKey | None":
        """
        From all enabled keys for this model's provider, return the one with
        the fewest currently ACTIVE queries — i.e. the least-loaded key.
        Keys that are individually rate-limited are excluded.
        """
        from server.models.queries.query import Query

        keys = list(aimodel.api_provider.api_keys.filter(enabled=True))
        if not keys:
            return None

        available = [
            k for k in keys
            if k.pk != (exclude.pk if exclude is not None else None) and not k.is_rate_limited()[0]
        ]
        if not available:
            return None

        def load(key: "ApiKey") -> int:
            return Query.objects.filter(apikey=key, status='ACTIVE').count()

        return min(available, key=load)
