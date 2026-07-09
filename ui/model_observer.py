"""
ModelObserver — a lightweight registry that maps Django ORM changes
to pyHtmlGui view callbacks across process boundaries.

Flow
----
1. Celery worker calls ``publish_model_event(instance, action)`` after an ORM write.
2. The consumer receives the event and calls ``UiApp.dispatch_session_event()``.
3. ``ModelObserver.dispatch()`` matches the event against registered
   ``(model_name, filter_dict)`` subscriptions using dict subset matching.
4. Matching callbacks fire on the registered view (via weakref).

Cleanup
-------
Subscriptions use weakrefs to the view. GC or calling ``unwatch(view)`` cleans up.
"""

from __future__ import annotations
import weakref
from collections import defaultdict
from typing import Any, Callable


class ModelObserver:
    def __init__(self):
        # {model_name: [{filter, callback_name, view_ref}]}
        self._subscriptions: dict[str, list[dict]] = defaultdict(list)

    def watch(
        self,
        model_class: type,
        filter: dict[str, Any] | None = None,
        callback_name: str | None = None,
        view: object | None = None,
        action: str | None = None,
    ) -> None:
        """Register a view callback for a model class + optional filter.

        Args:
            model_class: Django model class (e.g. ``Message``, ``AgentTaskCall``).
            filter: Dict of field=value pairs the event's filter_context
                    must contain (subset match).  Empty or None matches all.
            callback_name: Method name on *view* to call on match. The method
                           receives ``(pk, action, filter_context)``.
            view: The view instance (stored as weakref).
            action: Optional action filter (``"create"``, ``"update"``,
                    ``"delete"``).  None matches all actions.
        """
        model_name = model_class._meta.model_name
        if callback_name is not None and view is not None:
            if not hasattr(view, callback_name):
                raise ValueError(
                    f"ModelObserver: view {type(view).__name__} has no method "
                    f"'{callback_name}'"
                )
        self._subscriptions[model_name].append({
            "filter": filter or {},
            "callback_name": callback_name,
            "view_ref": weakref.ref(view) if view is not None else None,
            "action": action,
        })

    def unwatch(self, view: object) -> None:
        """Remove all subscriptions for *view*."""
        for model_name in list(self._subscriptions.keys()):
            self._subscriptions[model_name] = [
                e
                for e in self._subscriptions[model_name]
                if e["view_ref"] is not None and e["view_ref"]() is not view
            ]
            if not self._subscriptions[model_name]:
                del self._subscriptions[model_name]

    def unwatch_filter(self, model_class: type, filter: dict[str, Any]) -> None:
        """Remove subscriptions for *model_class* matching *filter*."""
        model_name = model_class._meta.model_name
        if model_name not in self._subscriptions:
            return
        self._subscriptions[model_name] = [
            e for e in self._subscriptions[model_name]
            if not all(k in e["filter"] and e["filter"][k] == v for k, v in filter.items())
        ]
        if not self._subscriptions[model_name]:
            del self._subscriptions[model_name]

    def dispatch(
        self,
        model_name: str,
        action: str,
        pk: int,
        filter_context: dict[str, Any],
    ) -> None:
        """Match and dispatch a model event to registered callbacks."""
        entries = self._subscriptions.get(model_name)
        if not entries:
            return
        alive = []
        for entry in entries:
            view = entry["view_ref"]()
            if view is None:
                continue  # dead weakref, dropped
            alive.append(entry)
            if entry.get("action") is not None and entry["action"] != action:
                continue
            if not self._matches(entry["filter"], filter_context):
                continue
            callback = getattr(view, entry["callback_name"], None)
            if callback is not None:
                try:
                    callback(pk, action, filter_context)
                except Exception:
                    pass
        if alive:
            self._subscriptions[model_name] = alive
        else:
            self._subscriptions.pop(model_name, None)

    @staticmethod
    def _matches(filter_dict: dict, context: dict) -> bool:
        """True when *filter_dict* is a subset of *context*."""
        for k, v in filter_dict.items():
            if k not in context or context[k] != v:
                return False
        return True
