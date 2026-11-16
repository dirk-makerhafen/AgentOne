"""Read-side observable data.

Every method returns an :class:`ObservableList` (evaluated rows + the exact
event keys that invalidate them) or an :class:`ObservableValue`.  The queryset
never escapes: arbitrary ``.filter()`` on a "live" list would produce data that
nothing publishes for, which is the bug this package exists to prevent.

If a view needs another live shape, add a method — the filter and its key are
written next to each other, which keeps them in sync.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Model, QuerySet


@dataclass(frozen=True)
class ObservableList:
    """Rows plus the keys whose events mean "refetch this list"."""

    model: type[Model]
    rows: tuple[Model, ...]
    keys: tuple[str, ...]


@dataclass(frozen=True)
class ObservableValue:
    """A single derived value (a count, a total) plus its invalidation keys."""

    value: Any
    keys: tuple[str, ...]


def pk_key(model: type[Model] | str, pk: int) -> str:
    name = model if isinstance(model, str) else model.__name__
    return f"{name}:{pk}"


def relation_key(model: type[Model] | str, field: str, value: int) -> str:
    name = model if isinstance(model, str) else model.__name__
    return f"{name}.{field}:{value}"


def root_key(model: type[Model] | str) -> str:
    name = model if isinstance(model, str) else model.__name__
    return f"{name}.root"


class ObservableBase:
    """Helpers shared by all domain APIs."""

    model: type[Model] | None = None

    def _list(self, queryset: QuerySet, *keys: str) -> ObservableList:
        return ObservableList(queryset.model, tuple(queryset), tuple(keys))

    def _value(self, value: Any, *keys: str) -> ObservableValue:
        return ObservableValue(value, tuple(keys))


class RowObservables(ObservableBase):
    """Fallback API for rows that the UI observes by primary key only."""

    def __init__(self, model: type[Model]):
        self.model = model

    def by_pk(self, pk: int) -> ObservableList:
        return self._list(self.model.objects.filter(pk=pk), pk_key(self.model, pk))
