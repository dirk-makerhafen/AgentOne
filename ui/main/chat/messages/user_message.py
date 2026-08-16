from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.chat.messages.message import MessageView
    from server.models.message import Message


class UserMessageView(ModelView):
    DOM_ELEMENT_CLASS = "msg-row"
    TEMPLATE_STR = '''
        <div class="msg-body">
            {% for message_part in  pyview.subject.parts.all() %}
                {{ message_part.content.get()}}
            {% endfor %}   
        </div>
        <div class="msg-foot">
            <span class="msg-time" title="{{pyview.subject.created_at}}">{{pyview.subject.created_at}}</span>
            <span class="msg-actions">
                <button class="msg-action-btn" title="Edit message" onclick="editMessage(this)">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"></path></svg>
                </button>
                <button class="msg-action-btn" title="Fork from here" onclick="pyview.fork({{pyview.subject.pk}})">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path></svg>
                </button>
                <button class="msg-copy-btn msg-action-btn" title="Copy" onclick="copyMsg(this)">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                </button>
            </span>
        </div>
    '''
    def __init__(self, subject: Message, parent: MessageView, **kwargs):
        super().__init__(subject, parent, **kwargs)

    def fork(self, message_id):
        self.parent.fork(message_id)
