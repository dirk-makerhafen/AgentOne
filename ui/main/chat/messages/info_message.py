from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.chat.messages.message import MessageView
    from server.models.message import Message


class InfoMessageView(ModelView):
    """Centered, UI-only system notice (role=INFO).

    Never sent to the LLM (``Message.save`` forces ``hide_from_context``).
    No fork/edit/copy actions — purely informational.
    """

    DOM_ELEMENT_CLASS = "msg-row"
    TEMPLATE_STR = '''
        <div class="msg-info" style="display:flex;justify-content:center;width:100%;margin:8px 0;">
            <div style="font-size:12px;opacity:0.75;background:var(--bg-soft, #f0f0f0);border-radius:12px;padding:4px 12px;text-align:center;">
                {% for message_part in pyview.subject.parts.all() %}{{ message_part.content.get()}}{% endfor %}
            </div>
        </div>
    '''

    def __init__(self, subject: Message, parent: MessageView, **kwargs):
        super().__init__(subject, parent, **kwargs)
