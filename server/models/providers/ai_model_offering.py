"""Provider↔model offering — the routable join between a provider and a model.

An :class:`AiModelOffering` row is one concrete way to call a model: a
provider-side model id, its free/paid conditions, its usage limits, its
observed health and its usage counters.  Sessions, responses and the rate
limiter pin an offering, while the model facts live on
:class:`~server.models.providers.ai_model.AiModel`.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.db.models import Sum
from django.utils import timezone

from server.models.base_model import BaseModel
from server.models.providers.health import HealthTrackedModel


class AiModelOffering(HealthTrackedModel, BaseModel):
    """One provider's offering of one raw model.

    ``enabled`` is the admin/manifest intent; the inherited ``status*`` fields
    record observed health (a provider that dropped the model, repeated 5xx,
    ...).  Selection prefers healthy rows and skips sticky failures.
    """

    api_provider = models.ForeignKey(
        "server.ApiProvider", on_delete=models.CASCADE, related_name="offerings"
    )
    model = models.ForeignKey(
        "server.AiModel", on_delete=models.CASCADE, related_name="offerings"
    )

    # Exact string to send as ``model`` on this provider.
    provider_model_id = models.CharField(max_length=512, default="", blank=True)

    # Denormalised display name (kept for backward compat / tests).  The
    # canonical name lives on ``model.name``; the loader keeps the two in sync.
    name = models.CharField(max_length=512, default="", blank=True)

    # Free-tier condition note from ``<provider>.free_models.md``.
    conditions = models.CharField(max_length=512, default="", blank=True)
    # Whether this offering is part of a verified free tier.
    is_free = models.BooleanField(default=False)
    # Date of the last free-tier verification (``YYYY-MM-DD``).
    free_verified = models.CharField(max_length=32, default="", blank=True)

    enabled = models.BooleanField(default=True)

    # Whether this offering runs on a local/self-hosted runtime.  A local
    # provider (e.g. Ollama) may still serve cloud models, so this is decided
    # per-offering, not per-provider.
    is_cloud = models.BooleanField(default=True)

    # Provider-specific overrides; empty means "use the raw model's value".
    context_window_override = models.IntegerField(null=True, blank=True, default=None)
    max_output_tokens_override = models.IntegerField(null=True, blank=True, default=None)

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

    # Maximum number of simultaneously active runs across all keys for this
    # offering.  0 = unlimited.
    limit_parallel_calls = models.IntegerField(default=0)

    # Timestamp of the last successful LLM call through this offering.
    last_usage = models.DateTimeField(null=True, blank=True)

    _LEGACY_MODEL_FIELDS = {
        "developer", "canonical_id", "family", "description", "leaderboard_id",
        "leaderboard_rank", "leaderboard_rank_is_estimate", "context_length",
        "max_prompt_tokens", "max_response_tokens", "max_output_tokens",
        "open_weights", "supports_reasoning", "requires_reasoning_echo",
        "supports_tool_call", "structured_output", "temperature", "vision",
        "audio", "video", "knowledge_cutoff", "filesize", "total_parameters",
        "active_parameters", "quantization",
    }

    def __init__(self, *args, **kwargs):
        self._legacy = {}
        for f in list(kwargs):
            if f in self._LEGACY_MODEL_FIELDS:
                self._legacy[f] = kwargs.pop(f)
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        if getattr(self, "model_id", None) is None:
            from server.models.providers.ai_model import AiModel

            raw = AiModel.objects.create(
                name=self.name or "unnamed",
                developer=self._legacy.pop("developer", "") or "",
                canonical_id=self._legacy.pop("canonical_id", "") or "",
                family=self._legacy.pop("family", "") or "",
                description=self._legacy.pop("description", "") or "",
                leaderboard_id=self._legacy.pop("leaderboard_id", "") or "",
                leaderboard_rank=self._legacy.pop("leaderboard_rank", None),
                leaderboard_rank_is_estimate=self._legacy.pop(
                    "leaderboard_rank_is_estimate", False
                ),
                context_length=self._legacy.pop("context_length", None) or 1000000,
                max_output_tokens=(
                    self._legacy.pop("max_output_tokens", None)
                    or self._legacy.pop("max_response_tokens", None)
                    or 1000000
                ),
                open_weights=self._legacy.pop("open_weights", False),
                supports_reasoning=self._legacy.pop("supports_reasoning", False),
                requires_reasoning_echo=self._legacy.pop("requires_reasoning_echo", False),
                supports_tool_call=self._legacy.pop("supports_tool_call", False),
                structured_output=self._legacy.pop("structured_output", False),
                temperature=self._legacy.pop("temperature", False),
                vision=self._legacy.pop("vision", False),
                audio=self._legacy.pop("audio", False),
                video=self._legacy.pop("video", False),
                knowledge_cutoff=self._legacy.pop("knowledge_cutoff", "") or "",
                filesize=self._legacy.pop("filesize", -1),
                total_parameters=self._legacy.pop("total_parameters", 0),
                active_parameters=self._legacy.pop("active_parameters", 0),
                quantization=self._legacy.pop("quantization", "") or "",
            )
            self.model = raw
        else:
            if self.name and self.model is not None and self.model.name != self.name:
                self.model.name = self.name
                self.model.save(update_fields=["name"])
            if "context_length" in self._legacy:
                self.context_window_override = self._legacy.pop("context_length")
            if "max_response_tokens" in self._legacy or "max_output_tokens" in self._legacy:
                self.max_output_tokens_override = (
                    self._legacy.pop("max_response_tokens", None)
                    or self._legacy.pop("max_output_tokens", None)
                )
            for f in (
                "open_weights", "supports_reasoning", "requires_reasoning_echo",
                "supports_tool_call", "structured_output", "temperature",
                "vision", "audio", "video",
            ):
                if f in self._legacy:
                    setattr(self.model, f, self._legacy.pop(f))
                    self.model.save(update_fields=[f])
        return super().save(*args, **kwargs)

    class Meta:
        ordering = ["model__name", "api_provider__name"]

    # ------------------------------------------------------------------
    # Raw-model fact passthroughs (read-only compatibility surface)
    # ------------------------------------------------------------------
    @property
    def family(self) -> str:
        return self.model.family if self.model_id else ""

    @property
    def description(self) -> str:
        return self.model.description

    @property
    def developer(self) -> str:
        return self.model.developer

    @property
    def canonical_id(self) -> str:
        return self.model.canonical_id

    @property
    def leaderboard_id(self) -> str:
        return self.model.leaderboard_id

    @property
    def leaderboard_rank(self):
        return self.model.leaderboard_rank

    @property
    def leaderboard_rank_is_estimate(self) -> bool:
        return self.model.leaderboard_rank_is_estimate

    @property
    def open_weights(self) -> bool:
        return self.model.open_weights

    @property
    def supports_reasoning(self) -> bool:
        return self.model.supports_reasoning

    @property
    def requires_reasoning_echo(self) -> bool:
        return self.model.requires_reasoning_echo

    @property
    def supports_tool_call(self) -> bool:
        return self.model.supports_tool_call

    @property
    def structured_output(self) -> bool:
        return self.model.structured_output

    @property
    def temperature(self) -> bool:
        return self.model.temperature

    @property
    def vision(self) -> bool:
        return self.model.vision

    @property
    def audio(self) -> bool:
        return self.model.audio

    @property
    def video(self) -> bool:
        return self.model.video

    @property
    def knowledge_cutoff(self) -> str:
        return self.model.knowledge_cutoff

    @property
    def filesize(self) -> int:
        return self.model.filesize

    @property
    def total_parameters(self) -> float:
        return self.model.total_parameters

    @property
    def active_parameters(self) -> float:
        return self.model.active_parameters

    @property
    def quantization(self) -> str:
        return self.model.quantization

    @property
    def context_length(self) -> int:
        return self.context_window_override or self.model.context_length

    @property
    def max_prompt_tokens(self) -> int:
        return self.context_length

    @property
    def max_response_tokens(self) -> int:
        return self.max_output_tokens_override or self.model.max_output_tokens

    @property
    def is_local_model(self) -> bool:
        """Whether this offering runs on a local/self-hosted runtime."""
        return not self.is_cloud

    # ------------------------------------------------------------------
    # Usage
    # ------------------------------------------------------------------
    @property
    def total_llm_queries(self) -> int:
        """Total number of queries made through this offering."""
        return self.related_queries.count()

    @property
    def total_prompt_tokens(self) -> int:
        """Total prompt tokens consumed across all responses for this offering."""
        result = self.related_responses.aggregate(total=Sum("prompt_tokens"))["total"]
        return result or 0

    @property
    def total_completion_tokens(self) -> int:
        """Total completion tokens consumed across all responses for this offering."""
        result = self.related_responses.aggregate(
            total=Sum("completion_tokens")
        )["total"]
        return result or 0

    @property
    def queries(self):
        """Return the related Query queryset for this offering."""
        from server.models.queries.query import Query

        return Query.objects.filter(related_response__aimodel=self).distinct()

    @property
    def responses(self):
        """Return the related Response queryset for this offering."""
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
        """Number of runs currently ACTIVE for this offering across all keys.

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
            offering = run.session_version.unresolved_aimodel()
            if offering is not None and offering.pk == self.pk:
                count += 1
        return count

    def is_rate_limited(self, exclude_taskrun_id: int | None = None) -> tuple[bool, str]:
        """Check all offering-level limits.

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
        """All AgentTaskCalls waiting due to this offering's rate limits, FIFO order."""
        from server.models.tasks.agent_task_call import (
            AgentTaskCall,
            pending_rate_limit_call_ids,
        )

        return AgentTaskCall.objects.filter(
            pk__in=pending_rate_limit_call_ids(model_id=self.pk)
        ).order_by("created_at")

    def __str__(self) -> str:
        return f"Offering:{self.model.name}@{self.api_provider.name}"
