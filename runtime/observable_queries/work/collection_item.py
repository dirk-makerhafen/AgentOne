"""Observable CollectionItem queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    relation_key,
)


class CollectionItemObservables(ObservableBase):
    def by_collection(self, collection_id: int) -> ObservableList:
        from server.models.collections.collection_item import CollectionItem

        return self._list(
            CollectionItem.objects.filter(collection_id=collection_id).order_by("created_at", "pk"),
            relation_key(CollectionItem, "collection", collection_id),
        )