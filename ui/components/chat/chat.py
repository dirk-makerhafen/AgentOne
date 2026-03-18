from threading import Lock
import types
import typing

from django.db.models.query import QuerySet
from server.models.agents.agent_instance import AgentInstance
from ui.pyHtmlGui.pyhtmlgui.pyhtmlguiInstance import PyHtmlGuiInstance
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView
from ui.components.chat.debuglog_view import DebugLogView
from ui.components.chat.query_view import QueryView
from ui.components.chat.response_view import ResponseView
from ui.components.chat.message_view import MessageView
from ui.components.chat.taskcall_view import TaskCallView



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







class ChatView(PyHtmlView):
    DOM_ELEMENT_CLASS = "resizable-container"
    DOM_ELEMENT_EXTRAS =  'data-orientation="vertical"'
    TEMPLATE_STR = """
        <div id="logArea_{{ pyview.subject.id }}" class="logArea resizable-panel conversation-log flex-column" data-size-pc="80">
            <div id="agent-status-ribbon_{{ pyview.subject.id }}" class="agent-status-ribbon agent-status-ribbon-hidden">
                <span class="status-text"></span>
            </div>
            {{ pyview.message_views.render() }}
        </div>
                    
        <div class="resizable-panel flex-row" data-size-pc="20" style="justify-content: end;">
            <div class="chat_user_input">
                <div id="messageInput_{{ pyview.subject.id }}" class="rich-text-input" contenteditable="true" data-placeholder="Enter your message..."></div>
            </div>
            <div class="chat-actions">
                <button id="sendMessageBtn_{{ pyview.subject.id }}" class="submit_button btn btn-success" type="submit" onclick="pyview.send_message(document.getElementById('messageInput_{{ pyview.subject.id }}').innerText)">Send</button>
            </div>

        </div>
        <script>
            parent = document.getElementById("{{pyview.uid}}");
            initializeSplitForContainer(parent.parentNode);
            /*pa rent.par nt.querySelectorAll('.resizable-container').forEach(container => {
                initializeSplitForContainer(container);
            });*/
        </script>
    """
    def __init__(self, subject: AgentInstance, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.f = subject
        print("subject.agent_task_calls", subject.agent_task_calls.all())
        self.s = [
            [ subject.conversation_messages, MessageView],
            [ subject.queries, QueryView],
            [ subject.responses, ResponseView],
            [ subject.debug_log_entries, DebugLogView ],
            [ subject.agent_task_calls.order_by("-created_at")[:10], TaskCallView ]
        ]
        print("HEHHEHRHERER", subject.agent_task_calls.all())
        self.message_views = QuerySetsView(subject=self.s, parent=self)


    def send_message(self, message):
        if message.strip():
            self.subject.latest_agent_instance_version.get_runtime_instance().add_user_message.delay(message=message)
        self.update()