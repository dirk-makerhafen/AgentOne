import types
import typing
from django.db.models.query import QuerySet
from threading import Lock
from .pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView


class QuerySetView(PyHtmlView):
    TEMPLATE_STR = '''
        {% for item in pyview.get_items() %}
            {{ item.render()}}
        {% endfor %}
    '''

    def __init__(self,
                 subject        : QuerySet,
                 parent         : PyHtmlView,
                 item_class     : type[PyHtmlView],
                 dom_element    : str             = PyHtmlView.DOM_ELEMENT,
                 dom_element_class    : str             = PyHtmlView.DOM_ELEMENT_CLASS,
                 sort_key       : typing.Callable|None = None,
                 sort_reverse   : bool            = False,
                 filter_function: typing.Callable|None = None,
                 **kwargs):

        self._item_class = item_class
        self.DOM_ELEMENT = dom_element
        self.DOM_ELEMENT_CLASS = dom_element_class
        self._kwargs = kwargs
        self._wrapped_data = []
        self._wrapped_data_lock = Lock()
        self.sort_key = sort_key
        self.sort_reverse = sort_reverse
        self.filter_function = filter_function
        if self.filter_function is None:
            self.filter_function = lambda x: False
        self.query = subject
        super().__init__(subject, parent)


    def get_items(self) -> list:
        data = [w for w in self._wrapped_data if not self.filter_function or self.filter_function(w) is False]
        if self.sort_key is None:
            return data
        else:
            return sorted(data, key=self.sort_key, reverse=self.sort_reverse)

    def set_visible(self, visible: bool) -> None:
        if self.is_visible == visible:  # not changed
            return
        self._wrapped_data_lock.acquire()
        super().set_visible(visible)
        for data in self._wrapped_data:
            data.delete(remove_from_dom=False)
        self._wrapped_data = []
        if self.is_visible is True:  # was set to invisible
            for item in self.query.all():
                self._wrapped_data.append(self._create_item(item))
        self._wrapped_data_lock.release()

    def _create_item(self, item):
        obj = self._item_class(subject=item, parent=self, **self._kwargs)
        obj._keep = item
        obj.element_index = types.MethodType(lambda x: x.parent.get_element_index(x), obj)
        obj.element_index_used = False
        return obj

    def _recreate(self):
        for data in self._wrapped_data:
            data.delete(remove_from_dom=False)
        self._wrapped_data = []
        for item in self.subject:
            self._wrapped_data.append(self._create_item(item))

    def get_element_index(self, element):
        element.element_index_used = True
        return self._wrapped_data.index(element)

