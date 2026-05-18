from __future__ import annotations
from django.db import models
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from server.models.base_model import BaseModel


class AiModel(BaseModel):
    api_provider = models.ForeignKey("server.ApiProvider", on_delete=models.CASCADE, related_name='aimodels')
    name = models.CharField(max_length=512)
    family = models.CharField(max_length=512, default="", blank=True)
    description = models.TextField(max_length=65000, default="", blank=True)

    enabled = models.BooleanField(default=True)

    context_length = models.IntegerField(default=1000000)
    is_cloud = models.BooleanField(default=True)
    filesize = models.IntegerField(default=-1)
    vision = models.BooleanField(default=False)
    billion_parameters = models.FloatField(default=0)

    max_prompt_tokens = models.IntegerField(default=1000000)
    max_response_tokens = models.IntegerField(default=1000000)

    # 0 = unlimited
    limit_request_per_day    = models.IntegerField(default=0)
    limit_request_per_minute = models.IntegerField(default=0)
    limit_tokens_per_day     = models.IntegerField(default=0)
    limit_tokens_per_minute  = models.IntegerField(default=0)

    # Maximum number of simultaneously active runs across all keys for this model.
    # 0 = unlimited.
    limit_parallel_calls = models.IntegerField(default=0)

    # ------------------------------------------------------------------
    # Usage counters (existing)
    # ------------------------------------------------------------------

    @property
    def total_llm_queries(self):
        return self.related_queries.count()

    @property
    def total_prompt_tokens(self):
        return self.related_responses.aggregate(total=Sum('prompt_tokens'))['total'] or 0

    @property
    def total_completion_tokens(self):
        return self.related_responses.aggregate(total=Sum('completion_tokens'))['total'] or 0

    @property
    def queries(self):
        return self.related_queries  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def responses(self):
        return self.related_responses  # pyright: ignore[reportAttributeAccessIssue]

    # ------------------------------------------------------------------
    # Rate limit checks
    # All counts use completed Responses (status=SUCCESS) as the source
    # of truth — that's what actually consumed provider capacity.
    # ------------------------------------------------------------------

    def requests_last_minute(self) -> int:
        since = timezone.now() - timedelta(seconds=60)
        return self.related_responses.filter(
            status='SUCCESS', created_at__gte=since
        ).count()

    def requests_today(self) -> int:
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.related_responses.filter(
            status='SUCCESS', created_at__gte=today
        ).count()

    def tokens_last_minute(self) -> int:
        since = timezone.now() - timedelta(seconds=60)
        result = self.related_responses.filter(
            status='SUCCESS', created_at__gte=since
        ).aggregate(total=Sum('prompt_tokens') + Sum('completion_tokens'))
        return result['total'] or 0

    def tokens_today(self) -> int:
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = self.related_responses.filter(
            status='SUCCESS', created_at__gte=today
        ).aggregate(total=Sum('prompt_tokens') + Sum('completion_tokens'))
        return result['total'] or 0

    def active_call_count(self) -> int:
        """Number of runs currently ACTIVE for this model across all keys."""
        from server.models.tasks.agent_task_run import AgentTaskRun
        from server.models.enums.task_enums import TaskRunStatus
        return AgentTaskRun.objects.filter(
            session_version__agent_version__profile__aimodel=self,
            status=TaskRunStatus.ACTIVE,
        ).count()

    def is_rate_limited(self) -> tuple[bool, str]:
        return False, ""
        """
        Check all model-level limits.
        Returns (is_limited: bool, reason: str).
        reason is empty string when not limited.
        """
        if self.limit_parallel_calls > 0:
            if self.active_call_count() >= self.limit_parallel_calls:
                return True, f"parallel_calls:{self.active_call_count()}/{self.limit_parallel_calls}"

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

    # ------------------------------------------------------------------
    # Pending calls (for UI)
    # ------------------------------------------------------------------

    def pending_calls(self):
        """
        All AgentTaskCalls currently waiting due to this model's rate limits,
        ordered by creation time (FIFO).
        """
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.enums.task_enums import TaskCallStatusDetail
        return AgentTaskCall.objects.filter(
            session_version__agent_version__profile__aimodel=self,
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
        ).order_by('created_at')

    def __str__(self):
        return "Model:" + self.name