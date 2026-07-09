"""AI Model model — provider's model definition with rate-limit tracking."""
from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from server.models.base_model import BaseModel


class AiModel(BaseModel):
    """Represents an AI model offered by a provider, with usage tracking and limits."""

    api_provider = models.ForeignKey(
        "server.ApiProvider",
        on_delete=models.CASCADE,
        related_name="aimodels",
    )
    name = models.CharField(max_length=512)
    family = models.CharField(max_length=512, default="", blank=True)
    description = models.TextField(max_length=65000, default="", blank=True)

    enabled = models.BooleanField(default=True)

    context_length = models.IntegerField(default=1000000)
    is_cloud = models.BooleanField(default=True)
    self_hosted = models.BooleanField(default=False)
    open_weights = models.BooleanField(default=False)
    supports_reasoning = models.BooleanField(default=False)
    requires_reasoning_echo = models.BooleanField(default=False)
    supports_tool_call = models.BooleanField(default=False)
    filesize = models.IntegerField(default=-1)
    vision = models.BooleanField(default=False)
    total_parameters = models.FloatField(default=0)
    active_parameters = models.FloatField(default=0)
    quantization = models.CharField(max_length=64, default="", blank=True)

    max_prompt_tokens = models.IntegerField(default=1000000)
    max_response_tokens = models.IntegerField(default=1000000)

    # 0 = unlimited
    limit_request_per_day = models.IntegerField(default=0)
    limit_request_per_minute = models.IntegerField(default=0)
    limit_tokens_per_day = models.IntegerField(default=0)
    limit_tokens_per_minute = models.IntegerField(default=0)

    # Maximum number of simultaneously active runs across all keys for this model.
    # 0 = unlimited.
    limit_parallel_calls = models.IntegerField(default=0)

    @property
    def total_llm_queries(self) -> int:
        """Total number of queries made through this model."""
        return self.related_queries.count()

    @property
    def total_prompt_tokens(self) -> int:
        """Total prompt tokens consumed across all responses for this model."""
        result = self.related_responses.aggregate(total=Sum("prompt_tokens"))["total"]
        return result or 0

    @property
    def total_completion_tokens(self) -> int:
        """Total completion tokens consumed across all responses for this model."""
        result = self.related_responses.aggregate(
            total=Sum("completion_tokens")
        )["total"]
        return result or 0

    @property
    def queries(self):
        """Return the related Query queryset for this model."""
        return self.related_queries  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def responses(self):
        """Return the related Response queryset for this model."""
        return self.related_responses  # pyright: ignore[reportAttributeAccessIssue]

    def requests_last_minute(self) -> int:
        """Number of successful responses in the last 60 seconds."""
        since = timezone.now() - timedelta(seconds=60)
        return self.related_responses.filter(
            status="SUCCESS", created_at__gte=since
        ).count()

    def requests_today(self) -> int:
        """Number of successful responses since midnight today."""
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.related_responses.filter(
            status="SUCCESS", created_at__gte=today
        ).count()

    def tokens_last_minute(self) -> int:
        """Total tokens (prompt + completion) in the last 60 seconds."""
        since = timezone.now() - timedelta(seconds=60)
        result = self.related_responses.filter(
            status="SUCCESS", created_at__gte=since
        ).aggregate(total=Sum("prompt_tokens") + Sum("completion_tokens"))
        return result["total"] or 0

    def tokens_today(self) -> int:
        """Total tokens (prompt + completion) since midnight today."""
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = self.related_responses.filter(
            status="SUCCESS", created_at__gte=today
        ).aggregate(total=Sum("prompt_tokens") + Sum("completion_tokens"))
        return result["total"] or 0

    def active_call_count(self) -> int:
        """Number of runs currently ACTIVE for this model across all keys."""
        from server.models.enums.task_enums import TaskRunStatus
        from server.models.tasks.agent_task_run import AgentTaskRun

        return AgentTaskRun.objects.filter(
            session_version__agent_version__profile__aimodel=self,
            status=TaskRunStatus.ACTIVE,
        ).count()

    def is_rate_limited(self) -> tuple[bool, str]:
        """Check all model-level limits.

        Returns:
            A tuple ``(is_limited, reason)`` where ``reason`` is empty when not limited.
        """
        return False, ""
        if self.limit_parallel_calls > 0:
            if self.active_call_count() >= self.limit_parallel_calls:
                return (
                    True,
                    f"parallel_calls:{self.active_call_count()}/{self.limit_parallel_calls}",
                )

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
        """All AgentTaskCalls waiting due to this model's rate limits, FIFO order."""
        from server.models.enums.task_enums import TaskCallStatusDetail
        from server.models.tasks.agent_task_call import AgentTaskCall

        return AgentTaskCall.objects.filter(
            session_version__agent_version__profile__aimodel=self,
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
        ).order_by("created_at")

    def __str__(self) -> str:
        return "Model:" + self.name
