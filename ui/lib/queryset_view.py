from __future__ import annotations
import types
import typing
from threading import Lock
from django.db.models.query import QuerySet
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.lib.model_view import ModelView

 
class QuerySetView(ModelView):
    """
    Renders a Django QuerySet as a list of child views.
 
    Each item in the queryset is wrapped in an instance of `item_class`.
    Items are created lazily when the view becomes visible and destroyed
    when it becomes invisible — avoiding DB hits for off-screen content.
 
    Usage:
        self.messages = QuerySetView(
            subject=instance.conversation_messages.order_by("created_at"),
            parent=self,
            item_class=MessageView,
        )

    Reactive lists
    --------------
    Pass ``observable_keys`` (a single key string or a list of them) to keep
    the list in sync with the ORM.  The usual key for a reverse foreign-key
    relation is the parent's helper, e.g.
    ``observable_keys=session.observables.messages`` (``"Message.session:<pk>"``).
    On ``create`` the new row is inserted and on ``delete`` it is removed —
    only that one wrapper is touched, never the whole list.  ``update`` events
    are left to the row views, which already subscribe to their own
    ``<Model>.pk:<pk>`` key.
    """
    TEMPLATE_STR = '''
        {% for item in pyview.get_items() %}
            {{ item.render() }}
        {% endfor %}
    '''
 
    def __init__(
        self,
        subject:         QuerySet,
        parent:          PyHtmlView,
        item_class:      type[PyHtmlView],
        dom_element:     str                   = PyHtmlView.DOM_ELEMENT,
        dom_element_class: str                 = PyHtmlView.DOM_ELEMENT_CLASS,
        sort_key:        typing.Callable | None = None,
        sort_reverse:    bool                  = False,
        filter_function: typing.Callable | None = None,
        observable_keys: str | list[str] | None = None,
        **kwargs,
    ):
        self._item_class      = item_class
        self.DOM_ELEMENT      = dom_element
        self.DOM_ELEMENT_CLASS = dom_element_class
        self._kwargs          = kwargs
        self._wrapped_data    = []
        self._lock            = Lock()
        self.sort_key         = sort_key
        self.sort_reverse     = sort_reverse
        self.filter_function  = filter_function or (lambda x: False)
        self.query            = subject
        self._observable_keys = []
        super().__init__(subject, parent)
        if observable_keys:
            self.set_observable_keys(observable_keys)
 
    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
 
    def get_items(self) -> list:
        data = [w for w in self._wrapped_data if not self.filter_function(w)]
        if self.sort_key is None:
            return data
        return sorted(data, key=self.sort_key, reverse=self.sort_reverse)

    def set_observable_keys(self, keys: str | list[str] | None) -> None:
        """(Re)subscribe this list to one or more observable keys.

        Replaces any keys previously registered by this view, so it can be
        re-pointed at runtime (e.g. when a project filter changes).  A view
        without a UI instance (unit tests) simply stays static.
        """
        from ui.lib.model_view import orm_subscribe, orm_unsubscribe_view

        try:
            orm_unsubscribe_view(self)
        except Exception:
            pass
        if isinstance(keys, str):
            keys = [keys]
        self._observable_keys = list(keys or [])
        for key in self._observable_keys:
            try:
                orm_subscribe(self, key, self._on_orm_event)
            except Exception:
                # Live refresh is an enhancement; a statically rendered list
                # is still correct, so never let registration break the view.
                pass
 
# ------------------------------------------------------------------
    # Visibility lifecycle
    # ------------------------------------------------------------------

    def _iter_subjects(self):
        """Yield the subjects to wrap — a QuerySet flattened via ``.all()`` or
        a plain list/tuple given directly as the subject."""
        if isinstance(self.query, (list, tuple)):
            return self.query
        return self.query.all()

    def set_visible(self, visible: bool) -> None:
        if self.is_visible == visible:
            return
        with self._lock:
            super().set_visible(visible)
            # Teardown always
            for item in self._wrapped_data:
                item.delete(remove_from_dom=False)
            self._wrapped_data = []
            # Rebuild only when becoming visible
            if self.is_visible is True:
                for item in self._iter_subjects():
                    self._wrapped_data.append(self._create_item(item))
 
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
 
    def _create_item(self, item) -> PyHtmlView:
        obj = self._item_class(subject=item, parent=self, **self._kwargs)
        obj._keep = item
        obj.element_index = types.MethodType(
            lambda x: x.parent.get_element_index(x), obj
        )
        obj.element_index_used = False
        return obj
 
    def _recreate(self):
        """Force a full rebuild of wrapped items from the queryset."""
        with self._lock:
            for item in self._wrapped_data:
                item.delete(remove_from_dom=False)
            self._wrapped_data = []
            for item in self._iter_subjects():
                self._wrapped_data.append(self._create_item(item))
 
    def get_element_index(self, element) -> int:
        element.element_index_used = True
        return self._wrapped_data.index(element)

    # ------------------------------------------------------------------
    # Reactive list maintenance
    # ------------------------------------------------------------------

    @staticmethod
    def _model_name(item) -> str:
        """Canonical model name for a row (proxy/deferred-safe)."""
        meta = getattr(item, "_meta", None)
        return getattr(meta, "model", type(item)).__name__

    def _subject_key(self, item) -> tuple[str, typing.Any]:
        """Identity of a row: ``(ModelName, pk)``.

        The model part matters: chat-style lists mix models, so two rows can
        share a pk without being the same row.
        """
        return (self._model_name(item), getattr(item, "pk", None))

    def _on_orm_event(self, key=None, model=None, pk=None, action=None, data=None) -> None:  # pylint: disable=unused-argument
        """Redis observable callback: add/remove one row on create/delete.

        ``update`` events are ignored here — the row views subscribe to their
        own ``<Model>.pk:<pk>`` key and re-render themselves.  An invisible
        list needs no work because ``set_visible(True)`` rebuilds from the
        live queryset.
        """
        if action not in ("create", "delete"):
            return
        if not self.is_visible:
            return
        with self._lock:
            if action == "create":
                self._insert_by_pk(model, pk)
            else:
                self._remove_by_pk(model, pk)

    def _place(self, obj, order: dict, subjects: list) -> None:
        """Position a new wrapper, keeping queryset order when unsorted."""
        if self.sort_key is not None:
            self._wrapped_data.append(obj)
            return
        new_index = order[self._subject_key(obj.subject)]
        insert_at = len(self._wrapped_data)
        for index, wrapper in enumerate(self._wrapped_data):
            if order.get(self._subject_key(wrapper.subject), len(subjects)) > new_index:
                insert_at = index
                break
        self._wrapped_data.insert(insert_at, obj)

    def _detach(self, obj) -> None:
        """Drop a wrapper that never made it into the DOM."""
        if obj in self._wrapped_data:
            self._wrapped_data.remove(obj)
        obj.delete(remove_from_dom=False)

    def _update_trailing(self, rendered: list, start_index: int) -> None:
        """Re-render rows after *start_index* that use the loop index."""
        for trailing in rendered[start_index:]:
            if getattr(trailing, "element_index_used", False):
                try:
                    trailing.update()
                except Exception:
                    pass

    def _insert_by_pk(self, model: str, pk: typing.Any) -> None:
        """Insert the row ``(model, pk)`` if it belongs to this list."""
        try:
            subjects = list(self._iter_subjects())
        except Exception:
            return
        target_key = (model, pk)
        order = {self._subject_key(item): index for index, item in enumerate(subjects)}
        if target_key not in order:
            # The new row does not match this list's queryset filters.
            return
        if any(self._subject_key(w.subject) == target_key for w in self._wrapped_data):
            return
        obj = self._create_item(subjects[order[target_key]])
        if self.filter_function(obj):
            obj.delete(remove_from_dom=False)
            return
        self._place(obj, order, subjects)
        rendered = self.get_items()
        try:
            rendered_index = rendered.index(obj)
        except ValueError:
            self._detach(obj)
            return
        try:
            inserted = self.insert_element(rendered_index, obj)
        except Exception:
            inserted = False
        if not inserted:
            self._detach(obj)
            return
        self._update_trailing(rendered, rendered_index + 1)

    def _remove_by_pk(self, model: str, pk: typing.Any) -> None:
        """Remove the wrapper for row ``(model, pk)`` if present."""
        target_key = (model, pk)
        wrapper = next(
            (w for w in self._wrapped_data if self._subject_key(w.subject) == target_key),
            None,
        )
        if wrapper is None:
            return
        rendered = self.get_items()
        try:
            rendered_index = rendered.index(wrapper)
        except ValueError:
            rendered_index = len(rendered)
        self._wrapped_data.remove(wrapper)
        try:
            wrapper.delete()
        except Exception:
            pass
        self._update_trailing(rendered, rendered_index + 1)

    def delete(self, remove_from_dom: bool = True) -> None:
        """Tear down the list and drop its redis subscriptions."""
        try:
            from ui.lib.model_view import orm_unsubscribe_view
            orm_unsubscribe_view(self)
        except Exception:
            pass
        super().delete(remove_from_dom=remove_from_dom)