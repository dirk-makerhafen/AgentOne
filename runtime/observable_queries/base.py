"""Internal helpers for building explicit observable ORM subscriptions."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db.models import Model, QuerySet

from runtime.observable_queries.subscription import ObservableSubscription
from server.models.base_model import ObservableMixin

Callback = Callable[[dict[str, Any]], None]


def _model_name(model: type[Model]) -> str:
    """Return the class name used by observable event keys."""
    return model._meta.model.__name__


def _require_observable_model(model: type[Model]) -> None:
    """Reject model classes that do not publish observable events."""
    if not isinstance(model, type) or not issubclass(model, ObservableMixin):
        raise TypeError(f"{model!r} does not support observable ORM events")


def _model_key(model: type[Model]) -> str:
    """Return the model-wide event key."""
    _require_observable_model(model)
    return _model_name(model)


def _subscribe_queryset(
    queryset: QuerySet,
    model: type[Model],
    keys: tuple[str, ...],
    callback: Callback,
    predicate: Callable[[dict[str, Any]], bool],
) -> ObservableSubscription:
    """Register first, read the initial snapshot, then release buffered events."""
    _require_observable_model(model)
    subscription = ObservableSubscription(callback, model, predicate)
    subscription.start(keys)
    try:
        items = [item.serialize_observable() for item in queryset]
        subscription.initialize(items)
    except Exception:
        subscription.close()
        raise
    return subscription


def _model_predicate(model: type[Model]) -> Callable[[dict[str, Any]], bool]:
    """Predicate for an unfiltered collection of one model."""
    expected = _model_name(model)
    return lambda item: item["model"] == expected


def _filtered_predicate(
    model: type[Model],
    base: Callable[[dict[str, Any]], bool],
    **expected_values: Any,
) -> Callable[[dict[str, Any]], bool]:
    """Compose a named, explicitly supported field condition."""
    expected = _model_name(model)
    return lambda item: (
        item["model"] == expected
        and base(item)
        and all(item.get(name) == value for name, value in expected_values.items())
    )
