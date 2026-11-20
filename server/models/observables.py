"""ORM -> UI event publishing.

There is no observer registry of callbacks any more. A model publishes an
explicit list of keys (see :mod:`runtime.observable_keys`); each connected tab
registers the keys it currently renders; Redis fans the event out to exactly
those tabs.

Structures
----------

``agentone:sse:watch:<client>``  STRING  JSON list of keys  (TTL, heartbeat)
``agentone:sse:keys:<key>``      SET     client ids         (reverse index)
``agentone:sse:<client>``        CHANNEL one per connected tab
``agentone:sse:seen:<client>``   STRING  reconnect marker

The watch string is authoritative. Connected tabs refresh its TTL on every
heartbeat; a hard-killed tab expires within ``WATCH_TTL`` and its reverse-index
entries are pruned lazily during the next fan-out.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import redis
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.utils import timezone

log = logging.getLogger(__name__)

WATCH_PREFIX = "agentone:sse:watch:"
KEYS_PREFIX = "agentone:sse:keys:"
CLIENT_PREFIX = "agentone:sse:"
SEEN_PREFIX = "agentone:sse:seen:"

#: Seconds a watch registration survives without a heartbeat.
WATCH_TTL = 60
#: Seconds after which a reconnect is treated as a fresh connection again.
SEEN_TTL = 300

#: Fields that lists may filter on; their previous value is captured on save so
#: a transition publishes both sides (e.g. archived true *and* false).
OBSERVABLE_FILTER_FIELDS = frozenset({
    "is_active",
    "is_archived",
    "is_pinned",
    "session_type",
    "status",
    "verify_status",
})

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return a shared Redis client (lazily created)."""
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def _norm(value: Any) -> Any:
    """Normalise a foreign-key value or enum member to what keys carry."""
    if value is None:
        return None
    value = getattr(value, "pk", value)
    return getattr(value, "value", value)


# ---------------------------------------------------------------------------
# client registry
# ---------------------------------------------------------------------------

def _watch_key(client_id: str) -> str:
    return WATCH_PREFIX + client_id


def watch_keys(client_id: str) -> list[str]:
    raw = get_redis().get(_watch_key(client_id))
    if not raw:
        return []
    try:
        return json.loads(raw)
    except ValueError:
        return []


def register_client(client_id: str, keys: list[str]) -> list[str]:
    """Replace one tab's watch set and update the reverse index.

    Returns the keys that were actually stored (deduplicated, whitespace-free).
    """
    keys = [key for key in dict.fromkeys(keys) if key and len(key) <= 200]
    r = get_redis()
    previous = set(watch_keys(client_id))
    current = set(keys)

    with r.pipeline() as pipe:
        for key in previous - current:
            pipe.srem(KEYS_PREFIX + key, client_id)
        for key in current - previous:
            pipe.sadd(KEYS_PREFIX + key, client_id)
        pipe.set(_watch_key(client_id), json.dumps(sorted(current)), ex=WATCH_TTL)
        pipe.set(SEEN_PREFIX + client_id, "1", ex=SEEN_TTL)
        pipe.execute()
    return keys


def touch_client(client_id: str) -> None:
    """Refresh the watch TTL from the SSE heartbeat."""
    try:
        get_redis().expire(_watch_key(client_id), WATCH_TTL)
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("Failed to refresh watch TTL for %s", client_id)


def reset_client(client_id: str) -> None:
    """Forget a tab (called when the stream ends cleanly).

    A reconnect may start before the dying stream's ``finally`` runs.  In that
    case the registration belongs to the *new* stream now: deleting it here
    would leave a live EventSource subscribed to nothing until its next DOM
    swap.  The caller unsubscribes its own pubsub first, so any remaining
    subscribers on this channel are the newer connection.
    """
    try:
        r = get_redis()
        channel = CLIENT_PREFIX + client_id
        subscribers = dict(r.pubsub_numsub(channel)).get(channel, 0)
        if subscribers:
            return
        for key in watch_keys(client_id):
            r.srem(KEYS_PREFIX + key, client_id)
        r.delete(_watch_key(client_id))
    except Exception:  # pylint: disable=broad-exception-caught
        log.exception("Failed to reset watch set for %s", client_id)


def mark_seen(client_id: str) -> bool:
    """Return True when this tab had a recent connection (i.e. a reconnect)."""
    r = get_redis()
    return not bool(r.set(SEEN_PREFIX + client_id, "1", ex=SEEN_TTL, nx=True))


# ---------------------------------------------------------------------------
# publishing
# ---------------------------------------------------------------------------

def publish_model_event(
    keys: list[str],
    instance: Any,
    action: str = "update",
    data: dict[str, Any] | None = None,
) -> None:
    """Publish one change to every tab watching each of ``keys``.

    Deferred to ``transaction.on_commit`` so a component refetch can never read
    the pre-commit row.  Outside an explicit transaction this runs immediately.
    """
    keys = list(dict.fromkeys(key for key in keys if key))
    if not keys:
        return
    envelope = {
        "model": type(instance).__name__,
        "pk": instance.pk,
        "action": action,
        "data": data,
        "at": timezone.now().isoformat(),
    }
    transaction.on_commit(lambda: _fan_out(keys, envelope))


def _fan_out(keys: list[str], envelope: dict[str, Any]) -> None:
    try:
        r = get_redis()
        with r.pipeline() as pipe:
            for key in keys:
                pipe.smembers(KEYS_PREFIX + key)
            members = pipe.execute()

        subscriptions: dict[str, list[str]] = {}
        for key, clients in zip(keys, members):
            for client in clients:
                subscriptions.setdefault(client, []).append(key)
        if not subscriptions:
            return

        with r.pipeline() as pipe:
            for client in subscriptions:
                pipe.exists(_watch_key(client))
            alive = pipe.execute()

        with r.pipeline() as pipe:
            for (client, client_keys), is_alive in zip(subscriptions.items(), alive):
                if not is_alive:
                    for key in client_keys:
                        pipe.srem(KEYS_PREFIX + key, client)
                    continue
                for key in client_keys:
                    pipe.publish(
                        CLIENT_PREFIX + client,
                        json.dumps({"key": key, **envelope}, default=str),
                    )
            pipe.execute()
    except Exception:  # pylint: disable=broad-exception-caught
        # A redis hiccup must never fail a database write.
        log.exception("Failed to publish observable event")


# ---------------------------------------------------------------------------
# model mixin
# ---------------------------------------------------------------------------

def _previous_state(instance: Any) -> dict[str, Any]:
    """Snapshot the values ``instance`` had before the pending write."""
    getter = getattr(instance, "get_dirty_fields", None)
    if getter is None:
        return {}
    try:
        dirty = getter(check_relationship=True)
    except Exception:  # pylint: disable=broad-exception-caught
        return {}

    state: dict[str, Any] = {}
    for field in instance._meta.concrete_fields:
        if not (field.is_relation or field.name in OBSERVABLE_FILTER_FIELDS):
            continue
        state[field.attname] = _norm(
            dirty.get(field.name, getattr(instance, field.attname))
        )
    return state


def _state_of(instance: Any, field_names) -> dict[str, Any]:
    """Snapshot only the fields named in an ``atomic_update`` call."""
    state: dict[str, Any] = {}
    for name in field_names:
        try:
            field = instance._meta.get_field(name)
        except FieldDoesNotExist:
            continue
        state[field.attname] = _norm(getattr(instance, field.attname))
    return state


class ObservableMixin:
    """Publish explicit keys whenever a row is created, changed or deleted."""

    def notify_observers(
        self,
        action: str = "update",
        previous: dict[str, Any] | None = None,
    ) -> None:
        from runtime.observable_keys import observable_keys  # keep imports flat

        publish_model_event(observable_keys(self, previous), self, action)

    def publish(self, action: str = "update", data: dict[str, Any] | None = None) -> None:
        """Compatibility shim for ``Model.publish("update")`` call sites."""
        self.notify_observers(action)

    def save(self, *args: Any, publish: bool = True, **kwargs: Any) -> Any:
        is_new = self._state.adding or self.pk is None
        previous = {} if is_new else _previous_state(self)
        result = super().save(*args, **kwargs)
        if publish:
            try:
                self.notify_observers("create" if is_new else "update", previous=previous)
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("Failed to notify observers for %s", type(self).__name__)
        return result

    def delete(self, *args: Any, publish: bool = True, **kwargs: Any) -> Any:
        pk = self.pk
        result = super().delete(*args, **kwargs)
        if publish and pk is not None:
            self.pk = pk
            try:
                self.notify_observers("delete")
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("Failed to publish delete for %s", type(self).__name__)
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
        previous = _state_of(self, fields) if publish else {}
        updated = type(self).objects.filter(pk=self.pk, **(expect or {})).update(**fields)
        if updated:
            for name, value in fields.items():
                try:
                    setattr(self, name, value)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
            if publish:
                try:
                    self.notify_observers(action, previous=previous)
                except Exception:  # pylint: disable=broad-exception-caught
                    log.exception("Failed to notify observers for %s", type(self).__name__)
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

        previous: dict[str, Any] = {}
        if publish:
            attnames = []
            for name in fields:
                try:
                    attnames.append(cls._meta.get_field(name).attname)
                except FieldDoesNotExist:
                    continue
            if attnames:
                previous = cls.objects.filter(pk=pk).values(*attnames).first() or {}

        updated = cls.objects.filter(pk=pk, **(expect or {})).update(**fields)
        if updated and publish:
            cls.publish_by_pk(pk, action, previous=previous)
        return updated

    @classmethod
    def publish_by_pk(
        cls,
        pk: Any,
        action: str = "update",
        data: dict[str, Any] | None = None,
        previous: dict[str, Any] | None = None,
    ) -> None:
        """Publish an event for a row touched by ``QuerySet.update()``."""
        if pk is None:
            return
        attnames = [
            field.attname
            for field in cls._meta.concrete_fields
            if field.is_relation or field.name in OBSERVABLE_FILTER_FIELDS
        ]
        row = cls.objects.filter(pk=pk).values("pk", *attnames).first()
        if row is None:
            return
        try:
            cls(**row).notify_observers(action, previous=previous)
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("Failed to publish %s pk=%s", cls.__name__, pk)
