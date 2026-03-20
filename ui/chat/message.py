from server.models.conversation_message import ConversationMessage
from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.pyHtmlGui.pyhtmlgui.view.queryset_view import QuerySetView

class MessagePartView(PyHtmlView):
    DOM_ELEMENT_CLASS = "MessagePartView message-part"
    TEMPLATE_STR = """
        {% if pyview.subject.content.content_type == 'image' %}
            <img src="{{ pyview.subject.content.content }}" class="chat-log-image" alt="User uploaded image">
        {% else %}
            {% if pyview.subject.content.content %}
                <p class="message-part-chat" style="white-space: pre;text-wrap:auto">{{pyview.subject.content.content}}</p>
            {% endif %}
        {% endif %}
    """

class MessageView(PyHtmlView):
    DOM_ELEMENT_CLASS = "MessageView conversation-log-item log-type-conversation user-log-item"
    TEMPLATE_STR = """
        <div class="message-header">
            <strong>[{{ pyview.subject.created_at }}]</strong> <strong>{{ pyview.subject.role }}</strong>
            <span class="message-actions">
                <i title="{{ 'Unpin from context' if pyview.subject.pin_to_context else 'Pin to context' }}" 
                   class="fa fa-thumb-tack pin-icon {{ 'pinned' if pyview.subject.pin_to_context else '' }}" 
                   onclick="pyview.toggle_pin()"></i>
                <i title="{{ 'Unhide this message from context' if pyview.subject.hide_from_context else 'Hide this message from context' }}" 
                   class="fa fa-eye-slash hide-icon {{ 'hide_from_context' if pyview.subject.hide_from_context else '' }}" 
                   onclick="pyview.toggle_hide()"></i>
            </span>
        </div>
        <div class="message-content" id="message_parts_container_{{ pyview.subject.id }}">
            {{ pyview.part_views.render() }}
        </div>
        <div class="message-query">
            query{{ pyview.subject.query }}
        </div>
        <div class="message-response">
            response{{ pyview.subject.response }}
        </div>
        <div class="message-tool_calls">
            tool_calls{{ pyview.subject.tool_calls }}
        </div>

    """
    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'style="order: {int(self.subject.created_at.timestamp())}"'
    
    def __init__(self, subject: ConversationMessage, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.part_views = QuerySetView(subject=subject.parts, parent=self, item_class=MessagePartView)

    def toggle_pin(self):
        self.subject.pin_to_context = not self.subject.pin_to_context
        if self.subject.pin_to_context:
            self.subject.hide_from_context = False
        self.subject.save()
        self.update()

    def toggle_hide(self):
        self.subject.hide_from_context = not self.subject.hide_from_context
        if self.subject.hide_from_context:
            self.subject.pin_to_context = False
        self.subject.save()
        self.update()
