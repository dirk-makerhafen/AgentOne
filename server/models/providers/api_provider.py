from __future__ import annotations
from django.db import models
from django.db.models import Sum
from server.models.queries.query import Query
from server.models.queries.response import Response
from server.models.base_model import BaseModel


class ApiProvider(BaseModel):
    name = models.CharField(max_length=512)
    url  = models.CharField(max_length=512, default="")

    # Maximum simultaneous active runs across ALL models for this provider.
    # Useful for local providers (e.g. Ollama) where concurrency is hardware-bound.
    # 0 = unlimited.
    limit_parallel_calls = models.IntegerField(default=0)

    # ------------------------------------------------------------------
    # Usage counters (existing)
    # ------------------------------------------------------------------

    @property
    def total_llm_queries(self):
        return Query.objects.filter(aimodel__api_provider=self).count()

    @property
    def total_prompt_tokens(self):
        return Response.objects.filter(
            query__aimodel__api_provider=self
        ).aggregate(total=Sum('prompt_tokens'))['total'] or 0

    @property
    def total_completion_tokens(self):
        return Response.objects.filter(
            query__aimodel__api_provider=self
        ).aggregate(total=Sum('completion_tokens'))['total'] or 0

    # ------------------------------------------------------------------
    # Rate limit checks
    # ------------------------------------------------------------------

    def active_call_count(self) -> int:
        """Total active runs across all models for this provider."""
        from server.models.tasks.agent_task_run import AgentTaskRun
        from server.models.enums.task_enums import TaskRunStatus
        return AgentTaskRun.objects.filter(
            agent_profile__aimodel__api_provider=self,
            status=TaskRunStatus.ACTIVE,
        ).count()

    def is_rate_limited(self) -> tuple[bool, str]:
        """
        Check provider-level parallel limit.
        Returns (is_limited: bool, reason: str).
        """
        if self.limit_parallel_calls > 0:
            active = self.active_call_count()
            if active >= self.limit_parallel_calls:
                return True, f"parallel_calls:{active}/{self.limit_parallel_calls}"
        return False, ""

    # ------------------------------------------------------------------
    # Pending calls (for UI)
    # ------------------------------------------------------------------

    def pending_calls(self):
        """All rate-limited calls for any model on this provider, FIFO order."""
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.enums.task_enums import TaskCallStatusDetail
        return AgentTaskCall.objects.filter(
            agent_instance_version__agent_version__profile__aimodel__api_provider=self,
            status_detail=TaskCallStatusDetail.WAITING_RATELIMIT,
        ).order_by('created_at')

    def __str__(self):
        return "ApiProvider:" + self.name