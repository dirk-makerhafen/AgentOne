"""
Redis-backed observable registry for the ORM→UI reactive layer.

The pyHtmlGui in-process observables only work when the subject and the view
live in the same process.  Celery workers mutate ORM entities in another
process, so we keep the observer registry in Redis:

Structures
----------
- ``agentone:obs:<observable_key>``   HASH  field=<instance_key> value=JSON list of function_ids
- ``agentone:uiq:<instance_key>``     LIST  one message per drained batch (instance queue)
- ``agentone:uikeys:<instance_key>``  SET   observable keys an instance is subscribed to (cleanup)

An observable_key is a stable string like ``AgentModel.pk:23`` or
``AgentModel.parent_project:12``.  Models expose them via a per-model
``Observables`` helper (e.g. ``agent.observables.pk``).

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

import json
from collections.abc import Sequence
from typing import Any

import redis
from django.conf import settings

OBS_PREFIX = "agentone:obs:"
QUEUE_PREFIX = "agentone:uiq:"
UKEYS_PREFIX = "agentone:uikeys:"

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return a shared Redis client (lazily created)."""
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def subscribe(instance_key: str, observable_key: str, function_id: int) -> None:
    """Register ``function_id`` of UI instance *instance_key* on *observable_key*."""
    r = get_redis()
    obs_key = OBS_PREFIX + observable_key
    fids = json.loads(r.hget(obs_key, instance_key) or "[]")
    if function_id not in fids:
        fids.append(function_id)
    r.hset(obs_key, instance_key, json.dumps(fids))
    r.sadd(UKEYS_PREFIX + instance_key, observable_key)


def unsubscribe(instance_key: str, observable_key: str, function_id: int) -> None:
    """Remove ``function_id`` of *instance_key* from *observable_key*."""
    r = get_redis()
    obs_key = OBS_PREFIX + observable_key
    fids = json.loads(r.hget(obs_key, instance_key) or "[]")
    if function_id in fids:
        fids.remove(function_id)
    if fids:
        r.hset(obs_key, instance_key, json.dumps(fids))
    else:
        r.hdel(obs_key, instance_key)
        r.srem(UKEYS_PREFIX + instance_key, observable_key)


def unsubscribe_all(instance_key: str) -> None:
    """Remove every subscription of *instance_key* (e.g. on last disconnect)."""
    r = get_redis()
    for observable_key in r.smembers(UKEYS_PREFIX + instance_key):
        r.hdel(OBS_PREFIX + observable_key, instance_key)
    r.delete(UKEYS_PREFIX + instance_key, QUEUE_PREFIX + instance_key)


def notify(
    observable_keys: Sequence[str],
    model: str,
    pk: int,
    action: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Push a message to every UI instance subscribed to any of *observable_keys*.

    Called by ORM ``notify_observers`` (which ``publish_model_event`` invokes
    for dual-publish during the migration).  Only queues that actually have
    an observer for one of the keys receive a message, and all their
    function_ids are batched into a single message per instance so the UI
    loop can coalesce repeated updates.  ``key`` is the first matched key
    (kept for backward compatibility); ``keys`` lists every matched key.
    """
    if not observable_keys:
        return
    r = get_redis()
    messages: dict[str, dict[str, Any]] = {}
    for observable_key in observable_keys:
        observers = r.hgetall(OBS_PREFIX + observable_key)
        if not observers:
            continue
        for instance_key, fids_json in observers.items():
            fids = json.loads(fids_json)
            if not fids:
                continue
            msg = messages.setdefault(instance_key, {
                "key": observable_key,
                "model": model,
                "pk": pk,
                "action": action,
                "data": data or {},
                "function_ids": [],
                "keys": [],
            })
            if observable_key not in msg["keys"]:
                msg["keys"].append(observable_key)
            for fid in fids:
                if fid not in msg["function_ids"]:
                    msg["function_ids"].append(fid)
    if not messages:
        return
    with r.pipeline() as p:
        for instance_key, msg in messages.items():
            p.rpush(QUEUE_PREFIX + instance_key, json.dumps(msg))
        p.execute()
