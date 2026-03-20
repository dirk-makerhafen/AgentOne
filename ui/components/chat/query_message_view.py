from server.models.queries.query_message import QueryMessage
from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.querySetView import QuerySetView


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
