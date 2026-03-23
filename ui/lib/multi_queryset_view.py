from __future__ import annotations
import types
import typing
from threading import Lock
from django.db.models.query import QuerySet
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

 
class MultiQuerySetView(ModelView):
    """
    Renders multiple querysets as a single merged list of child views,
    sorted by a common key (default: created_at timestamp for ordering).
 
    Each entry in `subject` is a (queryset, ViewClass) tuple. All items
    from all querysets are wrapped and merged into one flat list.
 
    Usage:
        self.timeline = MultiQuerySetView(
            subject=[
                (instance.conversation_messages.all(), MessageView),
                (instance.queries.all(),               QueryView),
                (instance.responses.all(),             ResponseView),
                (instance.agent_task_calls.all(),      TaskCallView),
            ],
            parent=self,
            sort_key=lambda w: w.subject.created_at.timestamp(),
        )
    """
    DOM_ELEMENT_EXTRAS = 'style="display: flex; flex-direction: column;"'
    TEMPLATE_STR = '''
        {% for item in pyview.get_items() %}
            {{ item.render() }}
        {% endfor %}
    '''
 
    def __init__(
        self,
        subject:         list[tuple[QuerySet, type[PyHtmlView]]],
        parent:          PyHtmlView,
        sort_key:        typing.Callable | None = None,
        sort_reverse:    bool                   = False,
        filter_function: typing.Callable | None = None,
        **kwargs,
    ):
        self.queries         = subject          # list of (queryset, ViewClass)
        self._wrapped_data   = []
        self._lock           = Lock()
        self.sort_key        = sort_key
        self.sort_reverse    = sort_reverse
        self.filter_function = filter_function or (lambda x: False)
        self._kwargs         = kwargs
        # PyHtmlView expects a single subject; use the first queryset as anchor
        super().__init__(subject[0][0], parent)
 
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
                for queryset, view_class in self.queries:
                    for item in queryset.all():
                        self._wrapped_data.append(
                            self._create_item(item, view_class)
                        )
 
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
 
    def _create_item(self, item, view_class: type[PyHtmlView]) -> PyHtmlView:
        obj = view_class(subject=item, parent=self, **self._kwargs)
        obj._keep = item
        obj.element_index = types.MethodType(
            lambda x: x.parent.get_element_index(x), obj
        )
        obj.element_index_used = False
        return obj
 
    def _recreate(self):
        """Force a full rebuild from all querysets."""
        with self._lock:
            for item in self._wrapped_data:
                item.delete(remove_from_dom=False)
            self._wrapped_data = []
            for queryset, view_class in self.queries:
                for item in queryset.all():
                    self._wrapped_data.append(
                        self._create_item(item, view_class)
                    )
 
    def get_element_index(self, element) -> int:
        element.element_index_used = True
        return self._wrapped_data.index(element)