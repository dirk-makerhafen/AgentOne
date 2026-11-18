"""Observable ApiProvider queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    root_key,
)


class ProviderObservables(ObservableBase):
    def root(self) -> ObservableList:
        from server.models.providers.api_provider import ApiProvider

        return self._list(ApiProvider.objects.order_by("name"), root_key(ApiProvider))