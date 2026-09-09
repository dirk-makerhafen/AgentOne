"""API Provider model — top-level provider with parallel-call limits."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

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

    # Stable identity for file-based loading: the ``providers/<slug>.md``
    # filename stem.  Upserts match on slug so a frontmatter ``name:`` rename
    # updates the row instead of creating a duplicate.  Auto-filled from
    # ``name`` on save when empty, so UI/test creations keep working.
    slug = models.CharField(max_length=128, unique=True)

    # Set to False by the provider loader when no manifest file supplies this
    # provider anymore (instead of deleting the row, so history stays intact).
    enabled = models.BooleanField(default=True)

    # LiteLLM provider prefix used when routing to this provider, e.g. ``groq``,
    # ``gemini`` or ``openrouter``.  Empty means the provider is OpenAI-compatible
    # and is routed through ``openai/`` with ``url`` as the api_base.
    litellm_prefix = models.CharField(max_length=64, default="", blank=True)

    # Whether the provider runs on a local machine (e.g. Ollama on localhost).
    # Local providers can still serve cloud models — those are distinguished
    # per-model via ``AiModel.is_cloud`` and are filtered out of the
    # "Local providers" settings section.
    is_local = models.BooleanField(default=False)

    # Maximum simultaneous active runs across ALL models for this provider.
    # Useful for local providers (e.g. Ollama) where concurrency is hardware-bound.
    # 0 = unlimited.
    limit_parallel_calls = models.IntegerField(default=0)


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

    def active_call_count(self, exclude_taskrun_id: int | None = None) -> int:
        """Total active runs across all models for this provider.

        ``exclude_taskrun_id`` optionally skips a run — the admission check
        inside ``RateLimitChecker`` runs from an already-``ACTIVE`` task run
        (``RunScheduler._apply_async`` transitions the run before the task
        body executes), so without this the checker counts *itself* against
        the parallel cap and a single call at ``limit_parallel_calls=1``
        deadlocks.
        """
        from server.models.enums.task_enums import TaskRunStatus
        from server.models.tasks.agent_task_run import AgentTaskRun

        qs = AgentTaskRun.objects.filter(status=TaskRunStatus.ACTIVE)
        if exclude_taskrun_id is not None:
            qs = qs.exclude(pk=exclude_taskrun_id)

        count = 0
        for run in qs:
            aimodel = run.session_version.unresolved_aimodel()
            if aimodel is not None and aimodel.api_provider_id == self.pk:
                count += 1
        return count

    def _responses_since(self, since, apikey=None) -> int:
        """Successful responses since *since*, optionally scoped to one key.

        When ``apikey`` is given only responses made through that key count —
        provider free-tier windows are per key, exactly like
        ``limit_parallel_calls``.
        """
        qs = Response.objects.filter(
            aimodel__api_provider=self,
            status="SUCCESS",
            created_at__gte=since,
        )
        if apikey is not None:
            qs = qs.filter(query__apikey=apikey)
        return qs.count()

    def requests_last_minute(self, apikey=None) -> int:
        """Number of successful responses in the last 60 seconds."""
        since = timezone.now() - timedelta(seconds=60)
        return self._responses_since(since, apikey=apikey)

    def requests_last_hour(self, apikey=None) -> int:
        """Number of successful responses in the last 60 minutes."""
        since = timezone.now() - timedelta(minutes=60)
        return self._responses_since(since, apikey=apikey)

    def requests_today(self, apikey=None) -> int:
        """Number of successful responses since midnight today."""
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self._responses_since(today, apikey=apikey)

    def tokens_since(self, since, apikey=None) -> int:
        """Total tokens (prompt + completion) in successful responses since a datetime."""
        qs = Response.objects.filter(
            aimodel__api_provider=self,
            status="SUCCESS",
            created_at__gte=since,
        )
        if apikey is not None:
            qs = qs.filter(query__apikey=apikey)
        result = qs.aggregate(total=Sum("prompt_tokens") + Sum("completion_tokens"))
        return result["total"] or 0

    def tokens_last_minute(self, apikey=None) -> int:
        since = timezone.now() - timedelta(seconds=60)
        return self.tokens_since(since, apikey=apikey)

    def tokens_last_hour(self, apikey=None) -> int:
        since = timezone.now() - timedelta(minutes=60)
        return self.tokens_since(since, apikey=apikey)

    def tokens_today(self, apikey=None) -> int:
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.tokens_since(today, apikey=apikey)

    @property
    def usable(self) -> bool:
        """Whether this provider can make LLM calls — has enabled keys or a default key."""
        return (
            self.api_keys.filter(enabled=True).exists()
            or bool(self.data.get("default_api_key"))
        )

    def _key_is_rate_limited(self, key) -> tuple[bool, str]:
        """Provider free-tier caps scoped to ONE key.

        Provider limits are PER API KEY — a provider with N enabled keys can
        drive N× the concurrency (each key gets its own parallel-slot, request
        and token windows).  The parallel census is live ACTIVE queries stamped
        with that key (``call_llm`` sets ``Query.apikey`` when a call enters
        ACTIVE), which is the same census ``ApiKey.active_call_count`` exposes.
        """
        if self.limit_parallel_calls > 0:
            active = Query.objects.filter(apikey=key, status="ACTIVE").count()
            if active >= self.limit_parallel_calls:
                return True, f"parallel_calls:{active}/{self.limit_parallel_calls}"

        if self.limit_request_per_minute > 0:
            rpm = self.requests_last_minute(apikey=key)
            if rpm >= self.limit_request_per_minute:
                return True, f"rpm:{rpm}/{self.limit_request_per_minute}"

        if self.limit_request_per_hour > 0:
            rph = self.requests_last_hour(apikey=key)
            if rph >= self.limit_request_per_hour:
                return True, f"rph:{rph}/{self.limit_request_per_hour}"

        if self.limit_request_per_day > 0:
            rpd = self.requests_today(apikey=key)
            if rpd >= self.limit_request_per_day:
                return True, f"rpd:{rpd}/{self.limit_request_per_day}"

        if self.limit_tokens_per_minute > 0:
            tpm = self.tokens_last_minute(apikey=key)
            if tpm >= self.limit_tokens_per_minute:
                return True, f"tpm:{tpm}/{self.limit_tokens_per_minute}"

        if self.limit_tokens_per_hour > 0:
            tph = self.tokens_last_hour(apikey=key)
            if tph >= self.limit_tokens_per_hour:
                return True, f"tph:{tph}/{self.limit_tokens_per_hour}"

        if self.limit_tokens_per_day > 0:
            tpd = self.tokens_today(apikey=key)
            if tpd >= self.limit_tokens_per_day:
                return True, f"tpd:{tpd}/{self.limit_tokens_per_day}"

        return False, ""

    def _provider_wide_is_rate_limited(self, exclude_taskrun_id: int | None) -> tuple[bool, str]:
        """Provider-wide counting used only for keyless configs.

        When the provider resolves requests through ``default_api_key`` (no
        ``ApiKey`` rows exist) there is no per-key dimension, so the caps
        aggregate across the whole provider via the active-run census.
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

    def is_rate_limited(self, apikey=None, exclude_taskrun_id: int | None = None) -> tuple[bool, str]:
        """Check provider rate caps, which apply PER API KEY.

        With a keyed provider the parallel-slot + request/token windows are
        counted per key (see :meth:`_key_is_rate_limited`).  This method
        aggregates: it reports the provider "rate limited" only when EVERY
        enabled key is at its own cap, which is what the composer picker and
        provider views need — a splintered key must never block its siblings.

        ``apikey=None`` with no ``ApiKey`` rows (keyless config via
        ``default_api_key``) falls back to provider-wide counting.  When a
        specific key is passed, its individual cap is returned.

        ``exclude_taskrun_id`` forwards to :meth:`active_call_count` for the
        keyless provider-wide parallel census so the run performing the
        admission check is not counted against itself.

        Returns:
            A tuple ``(is_limited, reason)`` where ``reason`` is empty when not limited.
        """
        if apikey is not None:
            return self._key_is_rate_limited(apikey)

        keys = list(self.api_keys.filter(enabled=True))
        if keys:
            reasons = []
            for key in keys:
                limited, reason = self._key_is_rate_limited(key)
                if not limited:
                    return False, ""
                reasons.append(reason)
            return True, ";".join(reasons) or "all_keys_capped"

        return self._provider_wide_is_rate_limited(exclude_taskrun_id)

    def pending_calls(self):
        """All rate-limited calls for any model on this provider, FIFO order."""
        from server.models.tasks.agent_task_call import (AgentTaskCall, pending_rate_limit_call_ids)
        return AgentTaskCall.objects.filter(pk__in=pending_rate_limit_call_ids(provider_id=self.pk)).order_by("created_at")

    def save(self, *args, **kwargs) -> Any:
        if not self.slug:
            import re

            base = re.sub(r"[^a-z0-9]+", "-", (self.name or "").lower()).strip("-") or "provider"
            slug, n = base, 2
            while (
                ApiProvider.objects.filter(slug=slug)
                .exclude(pk=self.pk)
                .exists()
            ):
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return "ApiProvider:" + self.name
