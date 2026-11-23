"""Observable AiModel queries."""
from __future__ import annotations

from runtime.observable_queries.base import (
    ObservableBase,
    ObservableList,
    relation_key,
)


class AiModelObservables(ObservableBase):
    def by_provider(self, provider_id: int) -> ObservableList:
        from server.models.providers.ai_model_offering import AiModelOffering as AiModel

        return self._list(
            AiModel.objects.filter(api_provider_id=provider_id).order_by("name"),
            relation_key(AiModel, "api_provider", provider_id),
        )