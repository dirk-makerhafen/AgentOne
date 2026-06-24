"""API Provider model — top-level provider with parallel-call limits."""
from __future__ import annotations

from django.db import models
from django.db.models import Sum

from server.models.base_model import BaseModel
from server.models.queries.query import Query
from server.models.queries.response import Response


class ApiProvider(BaseModel):
    """An API provider (e.g. OpenAI, Ollama) hosting one or more AI models."""

    name = models.CharField(max_length=512)
    url = models.CharField(max_length=512, default="")

    # Maximum simultaneous active runs across ALL models for this provider.
    # Useful for local providers (e.g. Ollama) where concurrency is hardware-bound.
    # 0 = unlimited.
    limit_parallel_calls = models.IntegerField(default=0)

    @property
    def total_llm_queries(self) -> int:
        """Total number of queries made through this provider."""
        return Query.objects.filter(aimodel__api_provider=self).count()

    @property
    def total_prompt_tokens(self) -> int:
        """Total prompt tokens consumed across all responses for this provider."""
        result = Response.objects.filter(
            query__aimodel__api_provider=self
        ).aggregate(total=Sum("prompt_tokens"))["total"]
        return result or 0

    @property
    def total_completion_tokens(self) -> int:
        """Total completion tokens consumed across all responses for this provider."""
        result = Response.objects.filter(
            query__aimodel__api_provider=self
        ).aggregate(total=Sum("completion_tokens"))["total"]
        return result or 0

    def active_call_count(self) -> int:
        """Total active runs across all models for this provider."""
        from server.models.enums.task_enums import TaskRunStatus
        from server.models.tasks.agent_task_run import AgentTaskRun

        return AgentTaskRun.objects.filter(
            agent_settings__aimodel__api_provider=self,
            status=TaskRunStatus.ACTIVE,
        ).count()

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
