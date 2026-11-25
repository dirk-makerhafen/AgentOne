from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.utils import timezone

from runtime.llm_errors import ModelUnavailableError

if TYPE_CHECKING:
    from server.models.providers.api_key import ApiKey
    from server.models.providers.ai_model_offering import AiModelOffering as AiModel


class RateLimitError(Exception):
    """Raised by RateLimitChecker.check() when no capacity is available.

    Caught separately in AgentTaskRun.apply() — does NOT trigger retry logic.
    ``wait=True`` means the checker deliberately chose to wait for a short
    cooldown (inside the route's wait budget) rather than fail over; callers
    must park the call instead of trying the next candidate.
    """

    def __init__(self, reason: str, *, wait: bool = False) -> None:
        self.reason = reason
        self.wait = wait
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
        """Whether the current cooling key may be bypassed right now.

        A zero ``remaining_wait`` means the key is not on a timed cooldown
        (e.g. a per-minute request cap): there is nothing to wait for, so
        rotating is always preferable.  A timed cooldown inside the wait
        budget is waited out; one beyond it triggers rotation.
        """
        if not self.auto_failover:
            return False
        if remaining_wait <= 0:
            return True
        if self.max_wait_seconds and self.max_wait_seconds > 0:
            return remaining_wait > self.max_wait_seconds
        return True


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
    def _current_taskrun_id(session) -> int | None:
        """The id of the run currently being executed by *session*, if any.

        ``AgentTaskRun.apply()`` stamps ``session._current_taskrun = self``
        before running the task body, and ``RunScheduler._apply_async`` has
        already transitioned that run to ``ACTIVE`` by then.  Excluding it
        from the parallel-call counts prevents the admission check from
        counting the very call it is deciding on.
        """
        current = getattr(session, "_current_taskrun", None)
        if current is None:
            return None
        pk = getattr(current, "pk", None)
        return int(pk) if pk is not None else None

    @staticmethod
    def check(
        aimodel: "AiModel",
        session=None,
        *,
        intent=None,
        api_key: "ApiKey | None" = None,
    ) -> RateLimitResult:
        """Check all rate-limit tiers and return the best available API key.

        When a runtime ``Session`` is supplied, key selection honours that
        session's route intent / key-stickiness policy.  ``api_key`` pins one
        exact key (strict offering+key routes); ``intent`` overrides the
        session's failover ladder for this call.
        """
        exclude = RateLimitChecker._current_taskrun_id(session)

        # 0. Observed-health gate — a 404 model id or revoked key will not
        #    recover by waiting, so skip the row instead of parking the call.
        if not aimodel.enabled:
            raise ModelUnavailableError("model:disabled")
        provider = aimodel.api_provider
        if provider is not None and not provider.enabled:
            raise ModelUnavailableError("provider:disabled")
        if aimodel.health_blocks_calls():
            raise ModelUnavailableError(
                f"model:{aimodel.status}:{aimodel.status_reason}"
            )

        # 1. Provider limits — per-API-key for keyed providers.  The aggregate
        #    gate trips only when EVERY enabled key is at its own cap, so a
        #    busy key never blocks a free sibling.
        limited, reason = aimodel.api_provider.is_rate_limited(exclude_taskrun_id=exclude)
        if limited:
            if "auth_error" in reason:
                raise ModelUnavailableError(f"provider:{reason}")
            raise RateLimitError(f"provider:{reason}")

        # 2. Model-level limits
        limited, reason = aimodel.is_rate_limited(exclude_taskrun_id=exclude)
        if limited:
            raise RateLimitError(f"model:{reason}")

        # 3. Key selection — skip if provider has no keys (keyless API)
        if not aimodel.api_provider.api_keys.exists():
            return RateLimitResult(selected_key=None)

        if api_key is not None:
            return RateLimitChecker._pinned_key_check(aimodel, api_key, intent)

        if session is not None:
            return RateLimitChecker._session_check(aimodel, session, intent=intent)

        key = RateLimitChecker._select_key(aimodel)
        if key is None:
            if aimodel.api_provider.all_enabled_keys_auth_failed():
                raise ModelUnavailableError("provider:auth_error")
            raise RateLimitError("no_key_available: all keys are rate-limited or disabled")
        return RateLimitResult(selected_key=key)

    @staticmethod
    def _key_wait_seconds(key: "ApiKey") -> float:
        """Remaining cooldown on *key*, in seconds (0 when not cooling)."""
        if not key.rate_limit_until:
            return 0.0
        return max(0.0, (key.rate_limit_until - timezone.now()).total_seconds())

    @staticmethod
    def _pinned_key_check(aimodel: "AiModel", api_key: "ApiKey", intent=None) -> RateLimitResult:
        """Admission for an explicitly pinned key (strict offering+key route)."""
        provider = aimodel.api_provider
        if api_key.api_provider_id != provider.pk:
            raise ModelUnavailableError("pinned_key:wrong_provider")
        if not api_key.enabled:
            raise ModelUnavailableError("pinned_key:disabled")
        limited, reason = api_key.is_rate_limited()
        if not limited:
            limited, reason = provider.is_rate_limited(apikey=api_key)
        if not limited:
            return RateLimitResult(selected_key=api_key)

        wait_seconds = 0 if intent is None else int(intent.wait_seconds or 0)
        if reason.startswith("auth"):
            raise ModelUnavailableError(f"pinned_key:{reason}")
        if wait_seconds <= 0:
            # Tests and strict pins fail immediately instead of parking a call
            # the user is not waiting for.
            raise ModelUnavailableError(f"pinned_key:{reason}")
        raise RateLimitError(f"pinned_key:{reason}", wait=True)

    @staticmethod
    def _session_check(aimodel: "AiModel", session, *, intent=None) -> RateLimitResult:
        """Key selection honouring the session's route intent.

        The session sticks to a single key per provider.  If that key is
        cooling and the route forbids rotation (or the remaining wait is
        inside the budget), the call is parked so it waits for *that* key.
        When rotation is allowed and the wait exceeds the budget, the next
        ready key of the same provider is selected and adopted.
        """
        current = session.current_provider_api_key(aimodel)
        provider = aimodel.api_provider

        policy = session.key_failover_policy()
        if intent is not None:
            policy = KeyFailoverPolicy(
                auto_failover=intent.allows_keys,
                max_wait_seconds=int(intent.wait_seconds or 0),
            )
        wait_budget = policy.max_wait_seconds

        if current is not None:
            limited, reason = current.is_rate_limited()
            if not limited:
                # Also honor provider per-key caps for the sticky key.
                prov_limited, prov_reason = provider.is_rate_limited(apikey=current)
                if not prov_limited:
                    return RateLimitResult(selected_key=current)
                limited, reason = prov_limited, prov_reason
            # Current key is cooling / provider-capped — decide whether we may rotate.
            if policy.switch_now(RateLimitChecker._key_wait_seconds(current)):
                key = RateLimitChecker._select_key(aimodel, exclude=current)
                if key is not None:
                    session.set_preferred_api_key(key)
                    return RateLimitResult(selected_key=key)
                # Every other key is busy too — this candidate has no capacity.
                if reason.startswith("auth"):
                    raise ModelUnavailableError(f"provider_keys:{reason}")
                raise RateLimitError(f"provider_keys:{reason}")
            if reason.startswith("auth"):
                raise ModelUnavailableError(f"key:{reason}")
            if wait_budget <= 0 and intent is not None and intent.failover == "none":
                raise ModelUnavailableError(f"key:{reason}")
            raise RateLimitError(f"key:{reason}", wait=True)

        key = RateLimitChecker._select_key(aimodel)
        if key is None:
            if aimodel.api_provider.all_enabled_keys_auth_failed():
                raise ModelUnavailableError("provider:auth_error")
            raise RateLimitError("no_key_available: all keys are rate-limited or disabled")
        # No stickiness mandate for a fresh provider — adopt the best key.
        session.set_preferred_api_key(key)
        return RateLimitResult(selected_key=key)

    @staticmethod
    def _select_key(aimodel: "AiModel", exclude: "ApiKey | None" = None) -> "ApiKey | None":
        """
        From all enabled keys for this model's provider, return the one with
        the fewest currently ACTIVE queries — i.e. the least-loaded key that
        is neither individually rate-limited nor at its provider per-key cap.
        """
        from server.models.queries.query import Query

        provider = aimodel.api_provider
        keys = list(provider.api_keys.filter(enabled=True))
        if not keys:
            return None

        available = []
        for k in keys:
            if k.pk == (exclude.pk if exclude is not None else None):
                continue
            if k.is_rate_limited()[0]:
                continue
            if provider.is_rate_limited(apikey=k)[0]:
                continue
            available.append(k)
        if not available:
            return None

        def load(key: "ApiKey") -> int:
            return Query.objects.filter(apikey=key, status='ACTIVE').count()

        return min(available, key=load)
