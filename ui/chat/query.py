from server.models.queries.query import Query
from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.queryset_view import QuerySetView
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


from server.models.queries.query_message import QueryMessage
from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.queryset_view import QuerySetView


class QueryMessagePartView(PyHtmlView):
    TEMPLATE_STR = """
    <div class="query-message-part-detail" id="query_message_part_{{ pyview.subject.id }}" data-part-id="{{ pyview.subject.id }}" data-part-index="{{ pyview.subject.index }}">
        <div class="message-header-nested">
            Part {{ pyview.subject.pk }} (~{{ pyview.subject.tokens }} tokens) <br>
            Index: {{pyview.subject.index}}<br>
             part: {{pyview.subject.conversation_message_part}}<br>
            part content: {{pyview.subject.conversation_message_part.content}}<br>
            part content: {{pyview.subject.conversation_message_part.content_template}}<br>

            Content: {{pyview.subject.content}}<br>
            content_prefix: {{pyview.subject.ontent_prefix}}<br>
            content_postfix: {{pyview.subject.content_postfix}}<br>
            content_template: {{pyview.subject.content_template}}<br>
            content_type: {{pyview.subject.content_type}}<br>
            tags: {{tags}}<br>
        </div>
        Compiled content:<br>
        <div id="query_message_part_content_{{ pyview.subject.id }}" class="message-content">
            <pre>{{ pyview.subject.compile(fail_on_error=False) }}</pre>
        </div>
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject

class QueryMessageView(PyHtmlView):
    TEMPLATE_STR = """
    <div id="query_message_{{ pyview.subject.id }}" class="query-message-detail" data-id="{{ pyview.subject.id }}" data-index="{{ pyview.subject.index }}">
        <div class="message-header-nested">
            <strong>{{ pyview.subject.role }}</strong> (~{{ pyview.subject.tokens }} tokens)
            <button class="btn btn-xs btn-default log-btn" onclick="pyview.toggle_parts()"><i class="fa fa-sitemap"></i> Parts</button>
        </div>
        <div class="query-message-parts-container {{ 'hidden' if pyview.is_parts_hidden else '' }}" id="query_message_parts_container_{{ pyview.subject.id }}">
            {{ pyview.query_message_parts_view.render() }}
        </div>
    </div>
    """
    def __init__(self, subject:QueryMessage, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_parts_hidden = True
        self.s = subject
        self.query_message_parts_view = QuerySetView(subject=subject.query_message_parts, parent=self, item_class=QueryMessagePartView)


    def toggle_parts(self):
        self.is_parts_hidden = not self.is_parts_hidden
        self.update()
