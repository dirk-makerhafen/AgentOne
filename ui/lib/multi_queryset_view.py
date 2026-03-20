
class QuerySetsView(PyHtmlView):
    DOM_ELEMENT_EXTRAS = 'style="display: flex; flex-direction: column;"'
    TEMPLATE_STR = '''
        {% for item in pyview.get_items() %}
            {{ item.render()}}
        {% endfor %}
    '''

    def __init__(self, subject: list[QuerySet], parent: PyHtmlView, dom_element: str = PyHtmlView.DOM_ELEMENT, dom_element_class: str = PyHtmlView.DOM_ELEMENT_CLASS, sort_key = None, sort_reverse: bool = False, filter_function = None, **kwargs):
        self.querys = subject
        self.querys = subject
        self._wrapped_data = []
        self._wrapped_data_lock = Lock()
        self.sort_key = sort_key
        self.sort_reverse = sort_reverse
        self.filter_function = filter_function
        self._kwargs = kwargs

        if self.filter_function is None:
            self.filter_function = lambda x: False
        self.queries = subject
        super().__init__(subject[0][0], parent)


    def set_visible(self, visible: bool) -> None:
        if self.is_visible == visible:  # not changed
            return
        self._wrapped_data_lock.acquire()
        super().set_visible(visible)
        for data in self._wrapped_data:
            data.delete(remove_from_dom=False)
        self._wrapped_data = []
        if self.is_visible is True:  # was set to invisible
            for query in self.queries:
                query, _class = query
                for item in query.all():
                    self._wrapped_data.append(self._create_item(item, _class))
        self._wrapped_data_lock.release()

    def _create_item(self, item, _class):
        obj = _class(item, self, **self._kwargs)
        obj._keep = item
        obj.element_index = types.MethodType(lambda x: x.parent.get_element_index(x), obj)
        obj.element_index_used = False
        return obj

    def get_items(self) -> list:
        data = [w for w in self._wrapped_data if self.filter_function(w) is False]
        if self.sort_key is None:
            return data
        else:
            return sorted(data, key=self.sort_key, reverse=self.sort_reverse)
        
    def _recreate(self):
        for data in self._wrapped_data:
            data.delete(remove_from_dom=False)
        self._wrapped_data = []
        for query in self.queries:
            query, _class = query
            for item in query.all():
                self._wrapped_data.append(self._create_item(item, _class))

    def get_element_index(self, element):
        element.element_index_used = True
        return self._wrapped_data.index(element)



