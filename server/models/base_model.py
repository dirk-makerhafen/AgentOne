"""Abstract base model with dirty-field tracking, JSON data support, and fork/dedup."""
from __future__ import annotations

import json
import traceback
from datetime import datetime
from typing import Any

from dirtyfields import DirtyFieldsMixin
from dirtyfields.dirtyfields import reset_state
from django.db import models
from django.utils import timezone


class Observables:
    """Base helper for building stable observable keys for an ORM instance.

    Subclasses add explicit ``@property`` names so IDEs can autocomplete them
    (e.g. ``agent.observables.parent_project``).  The base provides ``any``
    and ``pk`` plus a ``__getattr__`` fallback that derives a key for any
    model attribute by name — both produce identical key strings to the ones
    :meth:`BaseModel.notify_observers` publishes.

    Key format::

        <ModelName>            # "any" — the whole model
        <ModelName>.pk:<pk>
        <ModelName>.<field>:<value>
    """

    def __init__(self, model) -> None:
        self.model = model

    @property
    def any(self) -> str:
        return type(self.model).__name__

    @property
    def pk(self) -> str:
        return f"{self.any}.pk:{self.model.pk}"

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        model = self.__dict__.get("model")
        if model is None:
            raise AttributeError(name)
        # Prefer the *_pk / *_id column value (no related-object query).
        for attname in (f"{name}_pk", f"{name}_id", name):
            if hasattr(model, attname):
                return f"{self.any}.{name}:{getattr(model, attname)}"
        raise AttributeError(name)


class ObservableMixin:
    """Adds ``.observables`` to any model — including non-BaseModel ones
    (e.g. ``Project``, ``SkillModel``) that only observe from the other side
    of a relation.  Looks for a nested ``<ModelName>Observables`` class and
    falls back to the generic :class:`Observables`."""

    @property
    def observables(self):
        if not hasattr(self, "_observables") or self._observables is None:
            obs_cls = getattr(self.__class__, f"{self.__class__.__name__}Observables", None)
            if obs_cls is None:
                obs_cls = Observables
            self._observables = obs_cls(self)
        return self._observables


class BaseModel(ObservableMixin, DirtyFieldsMixin, models.Model):
    """Abstract base model providing created/updated timestamps, raw JSON data
    storage, and fork-based data deduplication."""

    created_at: datetime = models.DateTimeField(db_index=True, editable=False, auto_now_add=True)
    updated_at: datetime = models.DateTimeField(editable=False, auto_now=True)
    raw_data: str = models.TextField(max_length=100 * 1024 * 1024, default="", blank=True)

    class Meta:
        abstract = True

    @property
    def data(self) -> dict[str, Any]:
        """Return the parsed JSON content of ``raw_data`` (or the referenced fork's
        data).

        Results are cached on the instance as ``_data``.
        """
        if not hasattr(self, "_data") or self._data is None:
            source_raw_data = self.raw_data
            try:
                self._data = json.loads(source_raw_data) if source_raw_data else {}
            except Exception as e:
                self._data = {
                    "__error": (
                        f"Failed to load data for {self}: {e} {traceback.format_exc()}"
                    )
                }
        return self._data

    @data.setter
    def data(self, new_data: dict[str, Any]) -> None:
        """Set new data (copy-on-write — breaks the fork reference).
        """
        self._data = new_data

    def observable_keys(self) -> list[str]:
        """Return the observable keys this instance notifies on.

        Always includes the ``any`` and ``pk`` keys, plus one key per set FK
        (e.g. ``AgentModel.parent_project:12``) so observers registered on the
        other side of the relation (``project.observables.child_agents``) are
        notified too.
        """
        keys = [self.observables.any]
        if self.pk is not None:
            keys.append(self.observables.pk)
        for field in self._meta.fields:
            if isinstance(field, models.ForeignKey):
                fk_id = getattr(self, field.attname, None)
                if fk_id is not None:
                    keys.append(f"{self.observables.any}.{field.name}:{fk_id}")
        return keys

    def notify_observers(self, action: str = "update", data: dict[str, Any] | None = None) -> None:
        """Notify subscribed UI observers for this instance's observable keys.

        Observer-gated: :func:`runtime.observables.notify` only pushes to
        instance queues that actually subscribed to one of the keys.
        """
        from runtime import observables as obs
        obs.notify(
            self.observable_keys(),
            self.__class__.__name__,
            self.pk,
            action,
            data,
        )

    def save(self, *args: Any, **kwargs: Any) -> Any:
        """Save the model, auto-serialising ``_data`` to ``raw_data`` and tracking
        dirty fields for partial updates.

        Only fields that have changed are included in ``update_fields``, which
        reduces unnecessary DB writes.
        """
        now = timezone.now()
        if not self.pk and self.created_at is None:
            self.created_at = now

        _dirty_fields = self.get_dirty_fields(check_relationship=True)
        self.updated_at = now
        if hasattr(self, "_data"):
            new_raw_data = json.dumps(self.data)
            if self.raw_data != new_raw_data:
                self.raw_data = new_raw_data
                _dirty_fields["raw_data"] = self.raw_data

        if self.pk is not None:
            if "update_fields" not in kwargs:
                fields_to_update = list(_dirty_fields.keys())
                if "updated_at" not in fields_to_update:
                    fields_to_update.append("updated_at")
                if "raw_data" not in fields_to_update and "raw_data" in _dirty_fields:
                    fields_to_update.append("raw_data")
                if fields_to_update:
                    kwargs["update_fields"] = fields_to_update
            else:
                if "updated_at" not in kwargs["update_fields"]:
                    kwargs["update_fields"].append("updated_at")
                if (
                    "raw_data" in _dirty_fields
                    and "raw_data" not in kwargs["update_fields"]
                ):
                    kwargs["update_fields"].append("raw_data")

        r = super().save(*args, **kwargs)
        reset_state(
            sender=self.__class__,
            instance=self,
            update_fields=kwargs.get("update_fields", []),
        )
        return r
