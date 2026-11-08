"""Abstract base model with dirty-field tracking, JSON data support, and fork/dedup."""
from __future__ import annotations

import json
import traceback
from collections.abc import Callable
from datetime import datetime
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from dirtyfields import DirtyFieldsMixin
from dirtyfields.dirtyfields import reset_state
from django.db import models
from django.utils import timezone


class ObservableKeys:
    """Build observable keys for one model instance."""

    def __init__(self, model) -> None:
        self.model = model

    @property
    def any(self) -> str:
        return type(self.model).__name__

    @property
    def pk(self) -> str:
        return f"{self.any}.pk:{self.model.pk}"

    @property
    def noparents(self) -> str:
        """Key for rows with no ``parent_*`` foreign key set."""
        return f"{self.any}.noparents"

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        model = self.__dict__.get("model")
        if model is None:
            raise AttributeError(name)
        for attname in (f"{name}_pk", f"{name}_id", name):
            if hasattr(model, attname):
                return f"{self.any}.{name}:{getattr(model, attname)}"
        raise AttributeError(name)


class ObservableMixin:
    """Make Django model events observable through the Redis registry."""

    OBSERVABLE_EXCLUDED_FIELDS = frozenset({"raw_data"})

    @property
    def observables(self) -> ObservableKeys:
        if not hasattr(self, "_observables") or self._observables is None:
            keys_class = getattr(
                self.__class__,
                f"{self.__class__.__name__}ObservableKeys",
                ObservableKeys,
            )
            self._observables = keys_class(self)
        return self._observables

    def observable_keys(self) -> list[str]:
        """Return the general and foreign-key-specific event keys for this row."""
        keys = [self.observables.any]
        if self.pk is not None:
            keys.append(self.observables.pk)
        has_parent_field = False
        has_parent = False
        for field in self._meta.fields:
            if not isinstance(field, models.ForeignKey):
                continue
            is_parent_field = field.name.startswith("parent_")
            fk_id = getattr(self, field.attname, None)
            if fk_id is not None:
                keys.append(f"{self.observables.any}.{field.name}:{fk_id}")
                if is_parent_field:
                    has_parent = True
            elif is_parent_field:
                has_parent_field = True
        if has_parent_field and not has_parent:
            keys.append(self.observables.noparents)
        return keys

    def notify_observers(
        self,
        action: str = "update",
        data: dict[str, Any] | None = None,
        *,
        data_factory: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        """Publish this row's change to subscribers of its observable keys."""
        from runtime.observables import notify

        notify(
            self.observable_keys(),
            self.__class__.__name__,
            self.pk,
            action,
            data,
            data_factory=data_factory,
        )

    def serialize_observable(self) -> dict[str, Any]:
        """Serialize concrete model fields for observable callbacks."""
        data: dict[str, Any] = {
            "model": type(self)._meta.model.__name__,
            "pk": self.pk,
        }
        excluded = self.OBSERVABLE_EXCLUDED_FIELDS
        for field in self._meta.concrete_fields:
            if field.name in excluded or field.attname in excluded:
                continue
            data[field.attname] = getattr(self, field.attname)
        data["revision"] = data.get("updated_at") or data.get("created_at") or timezone.now()
        return json.loads(json.dumps(data, cls=DjangoJSONEncoder, default=str))

    def publish(self, action: str = "update", data: dict[str, Any] | None = None) -> None:
        from runtime.observables import publish_model_event

        if data is None:
            publish_model_event(self, action)
        else:
            publish_model_event(self, action, data=data)

    def save(self, *args: Any, publish: bool = True, **kwargs: Any) -> Any:
        """Save the row and publish its create or update event."""
        is_new = self._state.adding or self.pk is None
        result = super().save(*args, **kwargs)
        if publish:
            try:
                self.publish("create" if is_new else "update")
            except Exception:
                pass
        return result

    def delete(self, *args: Any, publish: bool = True, **kwargs: Any) -> Any:
        """Delete the row and publish its delete event."""
        pk = self.pk
        result = super().delete(*args, **kwargs)
        if publish:
            self.pk = pk
            try:
                self.publish("delete")
            except Exception:
                pass
            finally:
                self.pk = None
        return result

    def atomic_update(
        self,
        action: str = "update",
        expect: dict[str, Any] | None = None,
        publish: bool = True,
        **fields: Any,
    ) -> int:
        """Perform an atomic update and publish when the row was updated."""
        if (
            "updated_at" not in fields
            and any(field.name == "updated_at" for field in self._meta.fields)
        ):
            fields["updated_at"] = timezone.now()
        updated = type(self).objects.filter(pk=self.pk, **(expect or {})).update(**fields)
        if updated:
            for name, value in fields.items():
                try:
                    setattr(self, name, value)
                except Exception:
                    pass
            if publish:
                try:
                    self.publish(action)
                except Exception:
                    pass
        return updated

    @classmethod
    def atomic_update_by_pk(
        cls,
        pk: Any,
        action: str = "update",
        expect: dict[str, Any] | None = None,
        publish: bool = True,
        **fields: Any,
    ) -> int:
        """Perform an atomic update by primary key."""
        if (
            "updated_at" not in fields
            and any(field.name == "updated_at" for field in cls._meta.fields)
        ):
            fields["updated_at"] = timezone.now()
        updated = cls.objects.filter(pk=pk, **(expect or {})).update(**fields)
        if updated and publish:
            cls.publish_by_pk(pk, action)
        return updated

    @classmethod
    def publish_by_pk(
        cls,
        pk: Any,
        action: str = "update",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Publish an event using a narrow lookup for foreign-key values."""
        if pk is None:
            return
        from runtime.observables import publish_model_event

        fk_attnames = [
            field.attname
            for field in cls._meta.fields
            if isinstance(field, models.ForeignKey)
        ]
        row = cls.objects.filter(pk=pk).values("pk", *fk_attnames).first()
        if row is not None:
            try:
                publish_model_event(cls(**row), action, data=data)
            except Exception:
                pass


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
