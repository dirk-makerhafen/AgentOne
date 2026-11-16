"""
Redis-backed observable registry for the ORM→UI reactive layer.

The  in-process observables only work when the subject and the view
live in the same process.  Celery workers mutate ORM entities in another
process, so we keep the observer registry in Redis:

Structures
----------
- ``agentone:obs:<observable_key>``   HASH  field=<instance_key> value=JSON list of function_ids
- ``agentone:uiq:<instance_key>``     LIST  one message per drained batch (instance queue)
- ``agentone:uikeys:<instance_key>``  SET   observable keys an instance is subscribed to (cleanup)

An observable_key is a stable string like ``AgentModel.pk:23`` or
``AgentModel.parent_project:12``. Models expose them via a per-model
``ObservableKeys`` helper (e.g. ``agent.observables.pk``).

Flow
----
1. UI: ``ModelView.add_observable(subject, target_function)`` resolves the key
   (``subject.observables.pk``), registers a function_id and calls
   :func:`subscribe`.
2. Backend: the model's ``notify_observers`` computes the object's keys and
   calls :func:`notify`, which looks up each key's observers and RPUSHes a
   single message to each subscribed instance queue.
3. UI loop: ``BLPOP`` the instance queue, drain the whole list at once, dedupe
   by ``(key, function_id)``, resolve each id via the instance's
   ``_function_references`` and invoke the callback.
"""

from __future__ import annotations

import logging
import json
from collections.abc import Callable, Sequence
from typing import Any

import redis
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils import timezone
from redis.exceptions import WatchError

log = logging.getLogger(__name__)


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

    OBSERVABLE_EXCLUDED_FIELDS: frozenset[str] = frozenset()

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
        observable_keys = self.observable_keys()
        if not observable_keys:
            return
        r = get_redis()

        # Pub/sub fan-out feeds the htmx/SSE UI.  The envelope is small on
        # purpose -- SSE consumers only use the channel name as the event name
        # and refetch the fragment themselves, so no serialized object is needed.
        envelope = json.dumps(
            {
                "model": self.__class__.__name__,
                "pk": self.pk,
                "action": action,
                "keys": list(observable_keys),
            },
            default=str,
        )

        with r.pipeline() as p:
            for observable_key in observable_keys:
                p.publish(PUBSUB_PREFIX + observable_key, envelope)
            p.execute()





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


OBS_PREFIX = "agentone:obs:"
QUEUE_PREFIX = "agentone:uiq:"
UKEYS_PREFIX = "agentone:uikeys:"
# Redis pub/sub channels for the htmx/SSE UI.  One channel per observable key;
# the channel suffix *is* the event name the browser listens for
# (``hx-trigger="sse:Message.session:7"``).
PUBSUB_PREFIX = "agentone:pubsub:"

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return a shared Redis client (lazily created)."""
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def subscribe(instance_key: str, observable_key: str, function_id: int) -> None:
    """Register ``function_id`` of UI instance *instance_key* on *observable_key*."""
    _update_subscription(instance_key, observable_key, function_id, add=True)


def _update_subscription(
    instance_key: str,
    observable_key: str,
    function_id: int,
    *,
    add: bool,
) -> None:
    r = get_redis()
    obs_key = OBS_PREFIX + observable_key
    with r.pipeline() as pipeline:
        while True:
            try:
                pipeline.watch(obs_key)
                fids = json.loads(pipeline.hget(obs_key, instance_key) or "[]")
                if add:
                    if function_id not in fids:
                        fids.append(function_id)
                elif function_id in fids:
                    fids.remove(function_id)

                pipeline.multi()
                if fids:
                    pipeline.hset(obs_key, instance_key, json.dumps(fids))
                    pipeline.sadd(UKEYS_PREFIX + instance_key, observable_key)
                else:
                    pipeline.hdel(obs_key, instance_key)
                    pipeline.srem(UKEYS_PREFIX + instance_key, observable_key)
                pipeline.execute()
                return
            except WatchError:
                continue
            finally:
                pipeline.reset()


def unsubscribe(instance_key: str, observable_key: str, function_id: int) -> None:
    """Remove ``function_id`` of *instance_key* from *observable_key*."""
    _update_subscription(instance_key, observable_key, function_id, add=False)


def unsubscribe_all(instance_key: str) -> None:
    """Remove every subscription of *instance_key* (e.g. on last disconnect)."""
    r = get_redis()
    for observable_key in r.smembers(UKEYS_PREFIX + instance_key):
        r.hdel(OBS_PREFIX + observable_key, instance_key)
    r.delete(UKEYS_PREFIX + instance_key, QUEUE_PREFIX + instance_key)


def has_subscribers(observable_keys: Sequence[str]) -> bool:
    """Return whether any event key currently has registered observers."""
    r = get_redis()
    return any(r.hlen(OBS_PREFIX + key) for key in observable_keys)


def _extract_filter_context(instance: Any) -> dict[str, Any]:
    """Extract FK fields + resolved session_id from a model instance."""
    from django.db.models import ForeignKey, OneToOneField

    ctx: dict[str, Any] = {}
    for field in instance._meta.fields:
        if isinstance(field, (ForeignKey, OneToOneField)):
            ctx[field.attname] = getattr(instance, field.attname)
    if "session_id" not in ctx and hasattr(instance, "session_version"):
        try:
            if instance.session_version_id:
                ctx["session_id"] = instance.session_version.session_id
        except Exception:
            pass
    return ctx


def publish_model_event(
    instance: Any,
    action: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Publish a model change to subscribers of its observable keys."""
    event_data = {**_extract_filter_context(instance), **(data or {})}
    serialize = getattr(instance, "serialize_observable", None)
    observable_keys = getattr(instance, "observable_keys", None)

    if callable(serialize) and callable(observable_keys):
        def serialize_event() -> dict[str, Any]:
            current_instance = instance
            if action != "delete" and getattr(current_instance, "pk", None) is not None:
                refreshed = type(current_instance)._default_manager.filter(
                    pk=current_instance.pk
                ).first()
                if refreshed is not None:
                    current_instance = refreshed
            return {
                **_extract_filter_context(current_instance),
                **(data or {}),
                "object": current_instance.serialize_observable(),
            }

    notify_observers = getattr(instance, "notify_observers", None)
    if callable(notify_observers):
        try:
            if callable(serialize) and callable(observable_keys):
                notify_observers(action, event_data, data_factory=serialize_event)
            else:
                notify_observers(action, event_data)
        except Exception:
            log.exception(
                "Failed to publish observable event for %s pk=%s",
                type(instance).__name__,
                getattr(instance, "pk", None),
            )

