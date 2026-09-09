"""AI Model model — provider's model definition with rate-limit tracking."""
from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from server.models.base_model import BaseModel


class AiModel(BaseModel):
    """Represents an AI model offered by a provider, with usage tracking and limits."""

    api_provider = models.ForeignKey("server.ApiProvider", on_delete=models.CASCADE, related_name="aimodels")
    name = models.CharField(max_length=512)
    provider_model_id = models.CharField(max_length=512, default="", blank=True)
    family = models.CharField(max_length=512, default="", blank=True)
    description = models.TextField(max_length=65000, default="", blank=True)

    enabled = models.BooleanField(default=True)

    # Model-card facts (from ``models/<slug>.md`` frontmatter).
    developer = models.CharField(max_length=512, default="", blank=True)
    canonical_id = models.CharField(max_length=512, default="", blank=True)

    # Leaderboard identity + rank as ONE sortable integer.  Estimated ranks
    # (card ``leaderboard_rank_estimated: "~N"``) are stored as their numeric
    # value with ``leaderboard_rank_is_estimate`` set, so sorting just works.
    leaderboard_id = models.CharField(max_length=512, default="", blank=True)
    leaderboard_rank = models.IntegerField(null=True, default=None)
    leaderboard_rank_is_estimate = models.BooleanField(default=False)

    context_length = models.IntegerField(default=1000000)
    is_cloud = models.BooleanField(default=True)
    open_weights = models.BooleanField(default=False)
    supports_reasoning = models.BooleanField(default=False)
    requires_reasoning_echo = models.BooleanField(default=False)
    supports_tool_call = models.BooleanField(default=False)
    filesize = models.IntegerField(default=-1)
    vision = models.BooleanField(default=False)
    audio = models.BooleanField(default=False)
    video = models.BooleanField(default=False)
    total_parameters = models.FloatField(default=0)
    active_parameters = models.FloatField(default=0)
    quantization = models.CharField(max_length=64, default="", blank=True)

    max_prompt_tokens = models.IntegerField(default=1000000)
    max_response_tokens = models.IntegerField(default=1000000)

    # 0 = unlimited
    limit_request_per_minute = models.IntegerField(default=0)
    limit_request_per_hour = models.IntegerField(default=0)
    limit_request_per_day = models.IntegerField(default=0)
    limit_request_per_week = models.IntegerField(default=0)
    limit_request_per_month = models.IntegerField(default=0)
            
    limit_tokens_per_minute = models.IntegerField(default=0)
    limit_tokens_per_hour = models.IntegerField(default=0)
    limit_tokens_per_day = models.IntegerField(default=0)
    limit_tokens_per_week = models.IntegerField(default=0)
    limit_tokens_per_month = models.IntegerField(default=0)

    # Maximum number of simultaneously active runs across all keys for this model.
    # 0 = unlimited.
    limit_parallel_calls = models.IntegerField(default=0)

    @property
    def is_local_model(self) -> bool:
        """Whether this model runs on a local/self-hosted runtime.

        A model is considered local when it is not a cloud model.  A local
        provider (e.g. Ollama) may still serve cloud models, so this is
        decided per-model, not per-provider.
        """
        return not self.is_cloud


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

    def requests_last_hour(self) -> int:
        """Number of successful responses in the last 60 minutes."""
        since = timezone.now() - timedelta(minutes=60)
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

    def tokens_last_hour(self) -> int:
        """Total tokens (prompt + completion) in the last 60 minutes."""
        since = timezone.now() - timedelta(minutes=60)
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

    def active_call_count(self, exclude_taskrun_id: int | None = None) -> int:
        """Number of runs currently ACTIVE for this model across all keys.

        ``exclude_taskrun_id`` optionally skips a run — the admission check
        inside ``RateLimitChecker`` runs from an already-``ACTIVE`` task run,
        so without this the checker counts *itself* against the parallel cap
        and a single call at ``limit_parallel_calls=1`` deadlocks.
        """
        from server.models.enums.task_enums import TaskRunStatus
        from server.models.tasks.agent_task_run import AgentTaskRun

        qs = AgentTaskRun.objects.filter(status=TaskRunStatus.ACTIVE)
        if exclude_taskrun_id is not None:
            qs = qs.exclude(pk=exclude_taskrun_id)

        count = 0
        for run in qs:
            aimodel = run.session_version.unresolved_aimodel()
            if aimodel is not None and aimodel.pk == self.pk:
                count += 1
        return count

    def is_rate_limited(self, exclude_taskrun_id: int | None = None) -> tuple[bool, str]:
        """Check all model-level limits.

        ``exclude_taskrun_id`` forwards to :meth:`active_call_count` so the
        run performing the admission check is not counted against itself.

        Returns:
            A tuple ``(is_limited, reason)`` where ``reason`` is empty when not limited.
        """
        if self.limit_parallel_calls > 0:
            active = self.active_call_count(exclude_taskrun_id=exclude_taskrun_id)
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
        """All AgentTaskCalls waiting due to this model's rate limits, FIFO order."""
        from server.models.tasks.agent_task_call import (AgentTaskCall, pending_rate_limit_call_ids)
        return AgentTaskCall.objects.filter(pk__in=pending_rate_limit_call_ids(model_id=self.pk)).order_by("created_at")

    def __str__(self) -> str:
        return "Model:" + self.name
