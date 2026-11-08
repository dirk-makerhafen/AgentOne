"""DataCollection model — unified base for Streams (append-only) and Ordered Sets (mutable)."""
from __future__ import annotations

from django.db import models

from server.models.base_model import BaseModel
from server.models.observable import ObservableKeys



class DataCollection(BaseModel):
    """Unified model for both Streams (append-only, auto member/score) and
    Ordered Sets (mutable, user-defined member/score).

    The model carries its own data-flow configuration (sources, processor,
    reprocess settings) so each collection is self-contained.
    """

    class DataCollectionObservableKeys(ObservableKeys):
        """Explicit observable keys for an DataCollection (IDE autocomplete)."""
        @property
        def items(self):
            return f"CollectionItem.collection:{self.model.pk}"

        @property
        def parent_project(self):
            return f"DataCollection.parent_project:{self.model.parent_project_id}"
        
    COLLECTION_TYPES = [("stream", "Stream"), ("set", "Ordered Set")]

    name = models.CharField(max_length=255)
    parent_project = models.ForeignKey(
        "server.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="data_collections",
    )
    scope_key = models.CharField(max_length=32, default="global", editable=False)
    description = models.TextField(default="", blank=True)
    collection_type = models.CharField(max_length=10, choices=COLLECTION_TYPES, default="stream")
    is_active = models.BooleanField(default=True)

    # ── Data flow: sources ──────────────────────────────────────────────
    # JSON list: [
    #   {"type": "query",   "project": "...", "agent": ["..."], "session": ["..."], "function": ["..."]},
    #   {"type": "stream",  "stream": "..."},
    #   {"type": "set",      "set": "..."},
    # ]
    sources = models.JSONField(default=list, blank=True)

    # ── Data flow: processor ────────────────────────────────────────────
    # JSON object — the agent + function that transforms source items:
    # {"project": "...", "agent": "...", "session": "...", "function": "..."}
    # "session" may contain template vars like {source_agent.name}
    processor = models.JSONField(default=dict, blank=True)

    # ── Data flow: on_removed handler (sets only) ───────────────────────
    # Same shape as processor; runs when an item is removed from the source set.
    on_removed = models.JSONField(default=dict, blank=True)

    # ── For sets: member / score extraction ─────────────────────────────
    # Python expressions evaluated against the processor's result value.
    member_field = models.TextField(default="", blank=True,help_text="Python expression to extract the member (unique ID) from the item")
    score_field = models.TextField(default="", blank=True,help_text="Python expression to extract the score (float) from the item")

    # ── Reprocess / backfill settings ───────────────────────────────────
    retroactive_on_source_change = models.IntegerField(default=0,help_text="When source matching criteria change, max existing items to retroactively process (0 = off)")
    max_reprocess = models.IntegerField(default=0,help_text="When processor task is updated, max historical items to reprocess (0 = off)")

    class Meta:
        verbose_name = "Data Collection"
        verbose_name_plural = "Data Collections"
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["collection_type"]),
            models.Index(fields=["collection_type", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["scope_key", "name"],
                name="uniq_dc_scope_name",
            ),
        ]

    def save(self, *args, **kwargs):
        """Keep the portable uniqueness scope synchronized with its project FK."""
        project_id = getattr(self, "parent_project_id", None)
        self.scope_key = (
            f"project-{project_id}"
            if project_id is not None
            else "global"
        )
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"scope_key"}
        return super().save(*args, **kwargs)

    @classmethod
    def resolve_in_scope(cls, name: str, parent_project=None):
        """Resolve a collection in a project, falling back to the global scope."""
        if parent_project is not None:
            scoped = cls.objects.filter(name=name, parent_project=parent_project).first()
            if scoped is not None:
                return scoped
        return cls.objects.get(name=name, parent_project__isnull=True)

    def __str__(self) -> str:
        return f"{self.get_collection_type_display()}[{self.name}]"
