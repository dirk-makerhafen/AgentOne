"""API Provider model — top-level provider with parallel-call limits."""
from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from server.models.base_model import BaseModel
from server.models.queries.query import Query
from server.models.queries.response import Response


class ApiProvider(BaseModel):
    """An API provider (e.g. OpenAI, Ollama) hosting one or more AI models."""

    name = models.CharField(max_length=512)
    url = models.CharField(max_length=512, default="")

    # Whether the provider runs on a local machine (e.g. Ollama on localhost).
    # Local providers can still serve cloud models — those are distinguished
    # per-model via ``AiModel.is_cloud`` and are filtered out of the
    # "Local providers" settings section.
    is_local = models.BooleanField(default=False)

    # Maximum simultaneous active runs across ALL models for this provider.
    # Useful for local providers (e.g. Ollama) where concurrency is hardware-bound.
    # 0 = unlimited.
    limit_parallel_calls = models.IntegerField(default=0)

    # Free-tier rate limits, mirrors the ``AiModel`` limit family.  Configured
    # from the provider's ``free_info`` block in providers.yaml; 0 = unlimited.
    limit_request_per_hour = models.IntegerField(default=0)
    limit_request_per_day = models.IntegerField(default=0)
    limit_request_per_minute = models.IntegerField(default=0)
    limit_tokens_per_hour = models.IntegerField(default=0)
    limit_tokens_per_day = models.IntegerField(default=0)
    limit_tokens_per_minute = models.IntegerField(default=0)

    observable_fields = set([
        "pk",
        "is_local",
    ])

    @property
    def total_llm_queries(self) -> int:
        """Total number of queries made through this provider."""
        return Query.objects.filter(
            related_response__aimodel__api_provider=self
        ).distinct().count()

    @property
    def total_prompt_tokens(self) -> int:
        """Total prompt tokens consumed across all responses for this provider."""
        result = Response.objects.filter(
            aimodel__api_provider=self
        ).aggregate(total=Sum("prompt_tokens"))["total"]
        return result or 0

    @property
    def total_completion_tokens(self) -> int:
        """Total completion tokens consumed across all responses for this provider."""
        result = Response.objects.filter(
            aimodel__api_provider=self
        ).aggregate(total=Sum("completion_tokens"))["total"]
        return result or 0

    @property
    def observable_keys(self):
        return set([
            "ApiProvider",
            f"ApiProvider.pk:{self.pk}",
        ])

    def active_call_count(self) -> int:
        """Total active runs across all models for this provider."""
        from server.models.enums.task_enums import TaskRunStatus
        from server.models.tasks.agent_task_run import AgentTaskRun

        return AgentTaskRun.objects.filter(
            agent_settings__aimodel__api_provider=self,
            status=TaskRunStatus.ACTIVE,
        ).count()

    def _responses_since(self, since) -> int:
        return Response.objects.filter(
            aimodel__api_provider=self,
            status="SUCCESS",
            created_at__gte=since,
        ).count()

    def requests_last_minute(self) -> int:
        """Number of successful responses in the last 60 seconds."""
        since = timezone.now() - timedelta(seconds=60)
        return self._responses_since(since)

    def requests_last_hour(self) -> int:
        """Number of successful responses in the last 60 minutes."""
        since = timezone.now() - timedelta(minutes=60)
        return self._responses_since(since)

    def requests_today(self) -> int:
        """Number of successful responses since midnight today."""
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self._responses_since(today)

    def tokens_since(self, since) -> int:
        """Total tokens (prompt + completion) in successful responses since a datetime."""
        result = Response.objects.filter(
            aimodel__api_provider=self,
            status="SUCCESS",
            created_at__gte=since,
        ).aggregate(total=Sum("prompt_tokens") + Sum("completion_tokens"))
        return result["total"] or 0

    def tokens_last_minute(self) -> int:
        since = timezone.now() - timedelta(seconds=60)
        return self.tokens_since(since)

    def tokens_last_hour(self) -> int:
        since = timezone.now() - timedelta(minutes=60)
        return self.tokens_since(since)

    def tokens_today(self) -> int:
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.tokens_since(today)

    @property
    def usable(self) -> bool:
        """Whether this provider can make LLM calls — has enabled keys or a default key."""
        return (
            self.api_keys.filter(enabled=True).exists()
            or bool(self.data.get("default_api_key"))
        )

    def is_rate_limited(self) -> tuple[bool, str]:
        """Check provider-level parallel limit.

        Returns:
            A tuple ``(is_limited, reason)`` where ``reason`` is empty when not limited.
        """
        return False, ""
        if self.limit_parallel_calls > 0:
            active = self.active_call_count()
            if active >= self.limit_parallel_calls:
                return True, f"parallel_calls:{active}/{self.limit_parallel_calls}"

        if self.limit_request_per_minute > 0:
            rpm = self.requests_last_minute()
            if rpm >= self.limit_request_per_minute:
                return True, f"rpm:{rpm}/{self.limit_request_per_minute}"

        if self.limit_request_per_hour > 0:
            rph = self.requests_last_hour()
            if rph >= self.limit_request_per_hour:
                return True, f"rph:{rph}/{self.limit_request_per_hour}"

        if self.limit_request_per_day > 0:
            rpd = self.requests_today()
            if rpd >= self.limit_request_per_day:
                return True, f"rpd:{rpd}/{self.limit_request_per_day}"

        if self.limit_tokens_per_minute > 0:
            tpm = self.tokens_last_minute()
            if tpm >= self.limit_tokens_per_minute:
                return True, f"tpm:{tpm}/{self.limit_tokens_per_minute}"

        if self.limit_tokens_per_hour > 0:
            tph = self.tokens_last_hour()
            if tph >= self.limit_tokens_per_hour:
                return True, f"tph:{tph}/{self.limit_tokens_per_hour}"

        if self.limit_tokens_per_day > 0:
            tpd = self.tokens_today()
            if tpd >= self.limit_tokens_per_day:
                return True, f"tpd:{tpd}/{self.limit_tokens_per_day}"

        return False, ""

    def pending_calls(self):
        """All rate-limited calls for any model on this provider, FIFO order."""
        from server.models.enums.task_enums import TaskCallStatusDetail
        from server.models.tasks.agent_task_call import AgentTaskCall

        return AgentTaskCall.objects.filter(
            session_version__agent_version__profile__aimodel__api_provider=self,
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
        ).order_by("created_at")

    def __str__(self) -> str:
        return "ApiProvider:" + self.name
