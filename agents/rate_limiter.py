from django.core.cache import cache
from django.utils import timezone
from agents.models.agent_instance import AgentInstance

class RateLimitExceeded(Exception):
    """Custom exception raised when an agent instance exceeds its rate limit."""
    def __init__(self, message, time_to_reset=0):
        super().__init__(message)
        self.message = message
        self.time_to_reset = time_to_reset

class AgentRateLimiter:
    """
    Manages and enforces rate limits for AgentInstance objects.
    Tracks requests and token usage per minute, respecting hierarchical limits.
    This implementation uses atomic cache operations to be safe for concurrent execution.
    """
    CACHE_KEY_PREFIX = "agent_rate_limit"

    def _get_cache_key(self, agent_instance_pk, limit_type):
        """Generates a cache key for the current minute's usage."""
        now = timezone.now()
        return f"{self.CACHE_KEY_PREFIX}:{agent_instance_pk}:{limit_type}:{now.year}-{now.month}-{now.day}-{now.hour}-{now.minute}"

    def check_and_record_usage(self, agent_instance: AgentInstance, requests_cost: int = 1, tokens_cost: int = 0):
        """
        Atomically checks if the agent instance is within its rate limits for the current minute.
        If within limits, records the usage. If limits are exceeded, raises RateLimitExceeded.
        This operation is safe from race conditions.
        """
        effective_requests_limit_data = agent_instance.effective_max_requests_per_minute
        effective_tokens_limit_data = agent_instance.effective_max_token_per_minute

        max_requests_instance_pk, effective_max_requests = (None, None)
        max_tokens_instance_pk, effective_max_tokens = (None, None)

        if effective_requests_limit_data:
            max_requests_instance_pk, effective_max_requests = effective_requests_limit_data
        if effective_tokens_limit_data:
            max_tokens_instance_pk, effective_max_tokens = effective_tokens_limit_data

        # If no limits are defined anywhere in the hierarchy, there's nothing to do.
        if not max_requests_instance_pk and not max_tokens_instance_pk:
            return

        now = timezone.now()
        seconds_to_reset = 60 - now.second + 1
        req_key = None

        # --- Atomically check and increment requests ---
        if max_requests_instance_pk and effective_max_requests is not None:
            if requests_cost > 0:
                req_key = self._get_cache_key(max_requests_instance_pk, "requests")
                
                # Atomically add key with value 0 if it doesn't exist. Timeout is 60s for the minute.
                cache.add(req_key, 0, timeout=60)
                
                # Atomically increment and get the new value.
                new_requests_count = cache.incr(req_key, requests_cost)

                if new_requests_count > effective_max_requests:
                    # We've exceeded the limit. Atomically "refund" the cost and raise.
                    cache.decr(req_key, requests_cost)
                    raise RateLimitExceeded(
                        f"Agent instance {agent_instance.name} ({agent_instance.instance_pk}) exceeded requests per minute limit.",
                        time_to_reset=seconds_to_reset
                    )

        # --- Atomically check and increment tokens ---
        if max_tokens_instance_pk and effective_max_tokens is not None:
            if tokens_cost > 0:
                token_key = self._get_cache_key(max_tokens_instance_pk, "tokens")

                cache.add(token_key, 0, timeout=60)
                new_tokens_count = cache.incr(token_key, tokens_cost)

                if new_tokens_count > effective_max_tokens:
                    # The operation failed, so we must refund the request count that was already committed.
                    if req_key and requests_cost > 0:
                        cache.decr(req_key, requests_cost)
                    
                    # And refund the token cost as well.
                    cache.decr(token_key, tokens_cost)
                    
                    raise RateLimitExceeded(
                        f"Agent instance {agent_instance.name} ({agent_instance.instance_pk}) exceeded tokens per minute limit.",
                        time_to_reset=seconds_to_reset
                    )
        
# Instantiate the limiter for easy import and use
rate_limiter = AgentRateLimiter()
