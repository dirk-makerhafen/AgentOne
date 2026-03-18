from server.models.queries.query import Query
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView
from ui.components.chat.query_message_view import QueryMessageView

class QueryView(PyHtmlView):
    DOM_ELEMENT_CLASS = 'QueryView conversation-log-item log-type-llm llm-query-item'
    TEMPLATE_STR = """
        <div class="message-header">
            <strong>[{{ pyview.subject.created_at }}]</strong> <strong>LLM Query : </strong>
            {{ pyview.subject.tokens }} tokens
            <button class="btn btn-xs btn-default log-btn" onclick="pyview.toggle_raw()"><i class="fa fa-code"></i> raw</button>
        </div>
        <div id="raw_json_container_llm_query_{{ pyview.subject.id }}" class="message-content {{ 'hidden' if pyview.is_raw_hidden else '' }}">
            <pre>{{ pyview.subject.data }}</pre>
        <div id="query_messages_container_{{ pyview.subject.id }}" class="message-content query-messages-container">
            {{ pyview.query_messages_view.render() }}
        </div>
        </div>

    """
    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'style="order: {int(self.subject.created_at.timestamp())}"'
    
    def __init__(self, subject: Query, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_raw_hidden = True
        self.query_messages_view = QuerySetView(subject=subject.query_messages.order_by("index","pk"), parent=self, item_class=QueryMessageView)

    def toggle_raw(self):
        self.is_raw_hidden = not self.is_raw_hidden
        self.update()
