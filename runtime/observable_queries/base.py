"""Internal helpers for building explicit observable ORM subscriptions."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db.models import Model, QuerySet

from runtime.observable_queries.subscription import ObservableSubscription
from server.models.observables import ObservableMixin

Callback = Callable[[dict[str, Any]], None]


def _subscribe_queryset(
    queryset: QuerySet,
    model: type[Model],
    keys: tuple[str, ...],
    callback: Callback,
    predicate: Callable[[dict[str, Any]], bool],
) -> ObservableSubscription:
    """Subscribe before reading the initial snapshot and buffer concurrent events."""
    if not issubclass(model, ObservableMixin):
        raise TypeError(f"{model!r} does not support observable ORM events")

    subscription = ObservableSubscription(callback, model, predicate)
    subscription.start(keys)
    try:
        items = [item.serialize_observable() for item in queryset.order_by()]
        subscription.initialize(items)
    except Exception:
        subscription.close()
        raise
    return subscription
