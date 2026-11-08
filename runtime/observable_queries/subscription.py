"""Thread-safe callback subscriptions over the Redis observable event queue."""
from __future__ import annotations

import logging
import json
import os
import threading
import uuid
from collections.abc import Callable
from typing import Any

from django.db.models import Model

from runtime import observables

log = logging.getLogger(__name__)

_instance_key = f"observable-api:{uuid.uuid4().hex}"
_owner_pid = os.getpid()
_lock = threading.RLock()
_callbacks: dict[int, ObservableSubscription] = {}
_next_function_id = 1
_dispatcher: threading.Thread | None = None


def _ensure_dispatcher() -> None:
    global _dispatcher, _instance_key, _owner_pid
    with _lock:
        if _owner_pid != os.getpid():
            _owner_pid = os.getpid()
            _instance_key = f"observable-api:{uuid.uuid4().hex}"
            _callbacks.clear()
            _dispatcher = None
        if _dispatcher is not None and _dispatcher.is_alive():
            return
        _dispatcher = threading.Thread(
            target=_dispatch_loop,
            name="observable-api-dispatch",
            daemon=True,
        )
        _dispatcher.start()


def _dispatch_loop() -> None:
    """Drain this process's observer queue and invoke local callbacks."""
    global _dispatcher
    with _lock:
        instance_key = _instance_key
    queue_key = observables.QUEUE_PREFIX + instance_key
    while True:
        with _lock:
            if not _callbacks:
                _dispatcher = None
                return
        try:
            result = observables.get_redis().blpop(queue_key, timeout=2)
            if result is None:
                continue
            messages = [result[1]]
            redis_client = observables.get_redis()
            remaining = redis_client.lrange(queue_key, 0, -1)
            redis_client.ltrim(queue_key, len(remaining), -1)
            messages.extend(remaining)
            for raw_message in messages:
                observables_message = json.loads(raw_message)
                for function_id in observables_message.get("function_ids", []):
                    with _lock:
                        subscription = _callbacks.get(function_id)
                    if subscription is not None:
                        subscription.dispatch(observables_message)
        except Exception:
            log.exception("Observable callback dispatcher failed")
            threading.Event().wait(0.5)


class ObservableSubscription:
    """One callback subscription to a supported query shape.

    The callback receives a ``snapshot`` first, then ``upsert`` or ``remove``
    events. Call :meth:`close` when the observer no longer needs updates.
    """

    def __init__(
        self,
        callback: Callable[[dict[str, Any]], None],
        model: type[Model],
        predicate: Callable[[dict[str, Any]], bool],
    ) -> None:
        self.callback = callback
        self.model = model
        self.predicate = predicate
        self.keys: tuple[str, ...] = ()
        self.function_id: int | None = None
        self._closed = False
        self._initialized = False
        self._pending: list[dict[str, Any]] = []
        self._members: set[tuple[str, str]] = set()
        self._lock = threading.RLock()

    def start(self, keys: tuple[str, ...]) -> None:
        """Register keys before the caller runs the initial query."""
        global _next_function_id, _instance_key, _owner_pid, _dispatcher
        with _lock:
            if _owner_pid != os.getpid():
                _owner_pid = os.getpid()
                _instance_key = f"observable-api:{uuid.uuid4().hex}"
                _callbacks.clear()
                _dispatcher = None
            self.function_id = _next_function_id
            _next_function_id += 1
            _callbacks[self.function_id] = self
            self.keys = tuple(dict.fromkeys(keys))
            try:
                for key in self.keys:
                    observables.subscribe(_instance_key, key, self.function_id)
            except Exception:
                _callbacks.pop(self.function_id, None)
                for key in self.keys:
                    observables.unsubscribe(_instance_key, key, self.function_id)
                raise
        _ensure_dispatcher()

    def initialize(self, items: list[dict[str, Any]]) -> None:
        """Deliver the initial snapshot before any buffered concurrent update."""
        with self._lock:
            if self._closed:
                return
            self._members = {
                (str(item.get("model")), str(item.get("pk")))
                for item in items
            }
            self.callback({"type": "snapshot", "items": items})
            if self._closed:
                return
            while self._pending:
                self._deliver(self._pending.pop(0))
            self._initialized = True

    def dispatch(self, message: dict[str, Any]) -> None:
        """Buffer events until initialization or deliver them in queue order."""
        with self._lock:
            if self._closed:
                return
            if not self._initialized:
                self._pending.append(message)
                return
            self._deliver(message)

    def _deliver(self, message: dict[str, Any]) -> None:
        item = message.get("data", {}).get("object")
        model = message.get("model")
        pk = message.get("pk")
        if not isinstance(item, dict):
            log.error("Observable event has no serialized model payload: %s.%s", model, pk)
            return

        identity = (str(model), str(pk))
        revision = item.get("revision")
        if message.get("action") == "delete" or not self.predicate(item):
            if identity not in self._members:
                return
            self._members.remove(identity)
            event = {
                "type": "remove",
                "model": model,
                "pk": pk,
                "revision": revision,
            }
        else:
            self._members.add(identity)
            event = {"type": "upsert", "item": item, "revision": revision}
        try:
            self.callback(event)
        except Exception:
            log.exception("Observable callback failed for %s.%s", model, pk)

    def close(self) -> None:
        """Unregister the callback and all its Redis observable keys."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        if self.function_id is None:
            return
        with _lock:
            _callbacks.pop(self.function_id, None)
            for key in self.keys:
                observables.unsubscribe(_instance_key, key, self.function_id)
            if not _callbacks:
                observables.get_redis().delete(observables.QUEUE_PREFIX + _instance_key)

    def __enter__(self) -> ObservableSubscription:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
