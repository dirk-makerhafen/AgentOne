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
        <ModelName>.noparents  # root-level rows (no ``parent_*`` FK set)
    """

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
        """Key for root-level rows — no ``parent_*`` FK is set.

        Only models that actually declare a ``parent_*`` FK ever publish
        this (see :meth:`ObservableMixin.observable_keys`), so subscribing
        to it is a no-op for flat models like ``Project``.
        """
        return f"{self.any}.noparents"

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
    """Makes any Django model observable.

    Adds ``.observables`` (looks for a nested ``<ModelName>Observables``
    class, falls back to the generic :class:`Observables`), plus
    :meth:`observable_keys` and :meth:`notify_observers` so every model —
    including non-``BaseModel`` ones (e.g. ``Project``, ``WorkspaceModel``)
    — can publish to the Redis observable registry.  Only relies on
    ``pk`` / ``_meta``, so it works on plain ``models.Model`` subclasses.
    """

    @property
    def observables(self):
        if not hasattr(self, "_observables") or self._observables is None:
            obs_cls = getattr(self.__class__, f"{self.__class__.__name__}Observables", None)
            if obs_cls is None:
                obs_cls = Observables
            self._observables = obs_cls(self)
        return self._observables

    def observable_keys(self) -> list[str]:
        """Return the observable keys this instance notifies on.

        Always includes the ``any`` and ``pk`` keys, plus one key per set FK
        (e.g. ``AgentModel.parent_project:12``) so observers registered on the
        other side of the relation (``project.observables.child_agents``) are
        notified too.  Models that declare a ``parent_*`` FK additionally
        publish ``<Model>.noparents`` while every such FK is ``None``, so a
        root-level list can observe its own scope (``Project`` has no
        ``parent_*`` FK and therefore never emits it).
        """
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

    def publish(self, action: str = "update", data: dict[str, Any] | None = None) -> None:
        """Publish a model event for this instance (``create``/``update``/``delete``).

        Thin wrapper around :func:`runtime.events.publish_model_event` so
        call sites read ``msg.publish("create")`` instead of a lazy import
        plus a free function call.  The import stays lazy (inside the call)
        so tests patching ``runtime.events.publish_model_event`` keep
        intercepting these.
        """
        from runtime.events import publish_model_event
        if data is None:
            publish_model_event(self, action)
        else:
            publish_model_event(self, action, data=data)

    def save(self, *args: Any, publish: bool = True, **kwargs: Any) -> Any:
        """Save the row, then auto-publish ``create`` (new row) or ``update``.

        Pass ``publish=False`` for internal bookkeeping writes that no view
        should react to.  ``QuerySet.update()`` / ``bulk_create()`` bypass
        ``save()`` — use :meth:`atomic_update` for those so the event still
        fires on success.
        """
        is_new = self._state.adding or self.pk is None
        r = super().save(*args, **kwargs)
        if publish:
            try:
                self.publish("create" if is_new else "update")
            except Exception:
                pass
        return r

    def delete(self, *args: Any, publish: bool = True, **kwargs: Any) -> Any:
        """Delete the row, then auto-publish ``delete``.

        The pk is restored temporarily for key computation (Django clears it
        on delete).  Pass ``publish=False`` to skip.
        """
        pk = self.pk
        r = super().delete(*args, **kwargs)
        if publish:
            self.pk = pk
            try:
                self.publish("delete")
            except Exception:
                pass
            finally:
                self.pk = None
        return r

    def atomic_update(
        self,
        action: str = "update",
        expect: dict[str, Any] | None = None,
        publish: bool = True,
        **fields: Any,
    ) -> int:
        """Atomic single-row ``UPDATE`` bypassing :meth:`save`, publishing on success.

        For race-safe transitions (FSMs, admission checks) where a
        ``QuerySet.update()`` must win-or-lose atomically — ``save()`` would
        read-modify-write and clobber a concurrent transition.  ``expect``
        holds extra compare-and-set lookups (e.g. ``status="NEW"``); a
        return of ``0`` means the row was already in a different state.
        ``updated_at`` is bumped automatically when the model has that field.

        The written values are applied to ``self`` in-process (no wide
        ``refresh_from_db`` re-SELECT) — publishing only needs the pk and FK
        ids, which are already loaded — so a transition costs exactly one
        UPDATE.

        Returns the number of rows updated (0 or 1).
        """
        from django.utils import timezone
        if (
            "updated_at" not in fields
            and any(f.name == "updated_at" for f in self._meta.fields)
        ):
            fields["updated_at"] = timezone.now()
        n = type(self).objects.filter(pk=self.pk, **(expect or {})).update(**fields)
        if n:
            for k, v in fields.items():
                try:
                    setattr(self, k, v)
                except Exception:
                    pass
            if publish:
                try:
                    self.publish(action)
                except Exception:
                    pass
        return n

    @classmethod
    def atomic_update_by_pk(
        cls,
        pk: Any,
        action: str = "update",
        expect: dict[str, Any] | None = None,
        publish: bool = True,
        **fields: Any,
    ) -> int:
        """Class-level :meth:`atomic_update` when only the pk is at hand (FSM pattern).

        Runs a direct ``QuerySet.update()`` — the row is never fetched or
        materialized — then, on success, publishes via :meth:`publish_by_pk`.
        ``updated_at`` is bumped automatically when the model has that field.
        Returns the number of rows updated (0 = missing row or lost race).
        """
        from django.utils import timezone
        if (
            "updated_at" not in fields
            and any(f.name == "updated_at" for f in cls._meta.fields)
        ):
            fields["updated_at"] = timezone.now()
        n = cls.objects.filter(pk=pk, **(expect or {})).update(**fields)
        if n and publish:
            cls.publish_by_pk(pk, action)
        return n

    @classmethod
    def publish_by_pk(
        cls,
        pk: Any,
        action: str = "update",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Publish a model event for a row identified only by its pk.

        Observable keys (``Model``, ``Model.pk:<pk>`` and one per set FK) are
        built from a single narrow ``values()`` lookup, so the full row —
        including heavy payload columns (``raw_data``, ``carguments_json``, …)
        — is never materialized.  Safe no-op when the row is gone.
        """
        if pk is None:
            return
        from runtime.events import publish_model_event
        fk_attnames = [
            f.attname for f in cls._meta.fields if isinstance(f, models.ForeignKey)
        ]
        row = cls.objects.filter(pk=pk).values("pk", *fk_attnames).first()
        if row is None:
            return
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
