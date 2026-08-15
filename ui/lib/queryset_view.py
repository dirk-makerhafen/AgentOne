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
        super().__init__(subject, parent)
 
    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
 
    def get_items(self) -> list:
        data = [w for w in self._wrapped_data if not self.filter_function(w)]
        if self.sort_key is None:
            return data
        return sorted(data, key=self.sort_key, reverse=self.sort_reverse)
 
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