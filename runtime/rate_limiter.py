from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

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

    selected_key: "ApiKey"


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
    def check(aimodel: "AiModel") -> RateLimitResult:
        """Check all rate-limit tiers and return the best available API key."""
        # 1. Provider parallel limit
        limited, reason = aimodel.api_provider.is_rate_limited()
        if limited:
            raise RateLimitError(f"provider:{reason}")

        # 2. Model-level limits
        limited, reason = aimodel.is_rate_limited()
        if limited:
            raise RateLimitError(f"model:{reason}")

        # 3. Key selection
        key = RateLimitChecker._select_key(aimodel)
        if key is None:
            raise RateLimitError("no_key_available: all keys are rate-limited or disabled")

        return RateLimitResult(selected_key=key)

    @staticmethod
    def _select_key(aimodel: "AiModel") -> "ApiKey | None":
        """
        From all enabled keys for this model's provider, return the one with
        the fewest currently ACTIVE queries — i.e. the least-loaded key.
        Keys that are individually rate-limited are excluded.
        """
        from server.models.queries.query import Query

        keys = list(aimodel.api_provider.api_keys.filter(enabled=True))
        if not keys:
            return None

        available = [k for k in keys if not k.is_rate_limited()[0]]
        if not available:
            return None

        def load(key: "ApiKey") -> int:
            return Query.objects.filter(apikey=key, status='ACTIVE').count()

        return min(available, key=load)
