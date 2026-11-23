"""AI model catalog — provider-independent model facts.

An :class:`AiModel` row is the *raw* model (``thinkingmachines/inkling-small``).
It carries only facts that belong to the model itself: developer, family,
context window, capabilities, leaderboard identity, open weights, ...

Provider-specific availability (provider-side model id, free conditions,
limits, health, usage) lives on :class:`AiModelOffering`, the join row between
this catalog and :class:`ApiProvider`.
"""
from __future__ import annotations

from django.db import models
from django.db.models import Sum

from server.models.base_model import BaseModel


class AiModel(BaseModel):
    """Provider-independent model facts (the raw model catalog row)."""

    # Stable identity for file-based loading: the ``models/<slug>.md`` filename
    # stem.  Upserts match on slug so a frontmatter ``name:`` rename updates
    # the row instead of creating a duplicate.
    slug = models.CharField(max_length=256, unique=True, null=True, blank=True, default=None)

    name = models.CharField(max_length=512)
    developer = models.CharField(max_length=512, default="", blank=True)
    canonical_id = models.CharField(max_length=512, default="", blank=True, db_index=True)
    family = models.CharField(max_length=512, default="", blank=True)
    description = models.TextField(max_length=65000, default="", blank=True)

    # Leaderboard identity + rank as ONE sortable integer.  Estimated ranks
    # (card ``leaderboard_rank_estimated: "~N"``) are stored as their numeric
    # value with ``leaderboard_rank_is_estimate`` set, so sorting just works.
    leaderboard_id = models.CharField(max_length=512, default="", blank=True)
    leaderboard_rank = models.IntegerField(null=True, default=None)
    leaderboard_rank_is_estimate = models.BooleanField(default=False)

    # Size / capability facts.
    context_length = models.IntegerField(default=1000000)
    max_output_tokens = models.IntegerField(default=1000000)
    open_weights = models.BooleanField(default=False)
    supports_reasoning = models.BooleanField(default=False)
    requires_reasoning_echo = models.BooleanField(default=False)
    supports_tool_call = models.BooleanField(default=False)
    structured_output = models.BooleanField(default=False)
    temperature = models.BooleanField(default=False)
    vision = models.BooleanField(default=False)
    audio = models.BooleanField(default=False)
    video = models.BooleanField(default=False)
    knowledge_cutoff = models.CharField(max_length=64, default="", blank=True)
    filesize = models.IntegerField(default=-1)
    total_parameters = models.FloatField(default=0)
    active_parameters = models.FloatField(default=0)
    quantization = models.CharField(max_length=64, default="", blank=True)

    class Meta:
        ordering = ["name"]

    @property
    def is_local_model(self) -> bool:
        """Whether any offering of this model runs on a local runtime."""
        return self.offerings.filter(is_cloud=False).exists()

    @property
    def total_llm_queries(self) -> int:
        """Total number of queries made through any offering of this model."""
        from server.models.queries.query import Query

        return Query.objects.filter(
            related_response__aimodel__model=self
        ).distinct().count()

    @property
    def total_prompt_tokens(self) -> int:
        """Total prompt tokens consumed across all offerings of this model."""
        from server.models.queries.response import Response

        result = Response.objects.filter(aimodel__model=self).aggregate(
            total=Sum("prompt_tokens")
        )["total"]
        return result or 0

    @property
    def total_completion_tokens(self) -> int:
        """Total completion tokens consumed across all offerings of this model."""
        from server.models.queries.response import Response

        result = Response.objects.filter(aimodel__model=self).aggregate(
            total=Sum("completion_tokens")
        )["total"]
        return result or 0

    def save(self, *args, **kwargs):
        if not self.slug:
            import re

            base = (
                re.sub(r"[^a-z0-9]+", "-", (self.canonical_id or self.name or "").lower())
                .strip("-")
                or "model"
            )
            slug, n = base, 2
            while AiModel.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return "Model:" + self.name
