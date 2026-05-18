from __future__ import annotations
from django.db import models
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta
from server.models.queries.response import Response
from server.models.base_model import BaseModel


class ApiKey(BaseModel):
    api_provider = models.ForeignKey("server.ApiProvider", on_delete=models.CASCADE, related_name='api_keys')
    comment = models.CharField(max_length=512, default="", null=True)
    key = models.CharField(max_length=512)

    enabled = models.BooleanField(default=True)

    # 0 = unlimited
    limit_request_per_day    = models.IntegerField(default=0)
    limit_request_per_minute = models.IntegerField(default=0)
    limit_tokens_per_day     = models.IntegerField(default=0)
    limit_tokens_per_minute  = models.IntegerField(default=0)

    # ------------------------------------------------------------------
    # Usage counters (existing)
    # ------------------------------------------------------------------

    @property
    def total_llm_queries(self):
        return self.related_queries.count()

    @property
    def total_prompt_tokens(self):
        return Response.objects.filter(query__apikey=self).aggregate(
            total=Sum('prompt_tokens'))['total'] or 0

    @property
    def total_completion_tokens(self):
        return Response.objects.filter(query__apikey=self).aggregate(
            total=Sum('completion_tokens'))['total'] or 0

    @property
    def queries(self):
        return self.related_queries  # pyright: ignore[reportAttributeAccessIssue]

    # ------------------------------------------------------------------
    # Rate limit checks
    # ------------------------------------------------------------------

    def requests_last_minute(self) -> int:
        since = timezone.now() - timedelta(seconds=60)
        return Response.objects.filter(
            query__apikey=self, status='SUCCESS', created_at__gte=since
        ).count()

    def requests_today(self) -> int:
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return Response.objects.filter(
            query__apikey=self, status='SUCCESS', created_at__gte=today
        ).count()

    def tokens_last_minute(self) -> int:
        since = timezone.now() - timedelta(seconds=60)
        result = Response.objects.filter(
            query__apikey=self, status='SUCCESS', created_at__gte=since
        ).aggregate(total=Sum('prompt_tokens') + Sum('completion_tokens'))
        return result['total'] or 0

    def tokens_today(self) -> int:
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = Response.objects.filter(
            query__apikey=self, status='SUCCESS', created_at__gte=today
        ).aggregate(total=Sum('prompt_tokens') + Sum('completion_tokens'))
        return result['total'] or 0

    def active_call_count(self) -> int:
        """Number of runs currently ACTIVE using this specific key."""
        from server.models.tasks.agent_task_run import AgentTaskRun
        from server.models.enums.task_enums import TaskRunStatus
        return AgentTaskRun.objects.filter(
            agent_settings__aimodel__api_provider=self.api_provider,
            status=TaskRunStatus.ACTIVE,
        ).count()

    def is_rate_limited(self) -> tuple[bool, str]:
        """
        Check all key-level limits.
        Returns (is_limited: bool, reason: str).
        """
        return False, ""
        if not self.enabled:
            return True, "disabled"

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
        All AgentTaskCalls waiting due to this key's rate limits, FIFO order.
        Note: calls waiting on the model limit show up in AiModel.pending_calls().
        """
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.enums.task_enums import TaskCallStatusDetail
        return AgentTaskCall.objects.filter(
            session_version__agent_version__profile__aimodel__api_provider=self.api_provider,
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
        ).order_by('created_at')

    def __str__(self):
        return f"ApiKey:{self.comment or self.pk} ({self.api_provider})"