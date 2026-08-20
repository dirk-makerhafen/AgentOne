"""CollectionItem — a single item belonging to a DataCollection (stream or set).

Every item is the result of an AgentTaskCall (referenced by ``source_call``).
Stream items are append-only; set items can be added and removed.
"""
from __future__ import annotations

from django.db import models

from server.models.base_model import BaseModel


class CollectionItem(BaseModel):
    """A single item in a DataCollection (stream or set).

    Fields
    ------
    collection : FK -> DataCollection
        The stream or set this item belongs to.
    source_call : FK -> AgentTaskCall (nullable)
        The agent task call whose result produced this item.
    member : str
        Unique identifier for the item *within its collection*
        (e.g. ``"email:123"``, a content hash, …).
    score : float
        Ordering value — typically a timestamp for streams,
        or a user-chosen field for sets.
    value : JSON
        The actual payload (processor result data).
    """

    class CollectionItemObservables(Observables):
        """Explicit observable keys for an CollectionItem (IDE autocomplete)."""
        
    collection = models.ForeignKey("DataCollection",on_delete=models.CASCADE,related_name="items")
    source_call = models.ForeignKey("server.AgentTaskCall",on_delete=models.SET_NULL,null=True,blank=True,default=None,related_name="collection_items")
    source_item = models.ForeignKey("self",on_delete=models.SET_NULL,null=True,blank=True,default=None,related_name="derived_items",help_text="The upstream CollectionItem whose propagation created this item")

    member = models.CharField(max_length=1024)
    score = models.FloatField(default=0.0)
    value = models.JSONField(default=dict, blank=True)


    class Meta:
        verbose_name = "Collection Item"
        verbose_name_plural = "Collection Items"
        unique_together = [("collection", "member")]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["score"]),
            models.Index(fields=["collection", "score"]),
        ]

    def __str__(self) -> str:
        return f"[{self.collection.name}] {self.member} (score={self.score})"
