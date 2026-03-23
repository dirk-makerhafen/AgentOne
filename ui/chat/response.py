from __future__ import annotations
from ui.lib.model_view import ModelView


class ResponseView(ModelView):
    DOM_ELEMENT_CLASS = "ResponseView conversation-log-item log-type-llm"

    TEMPLATE_STR = """
        <div class="message-header">
            <span class="message-time">{{ pyview.subject.created_at.strftime('%H:%M:%S') }}</span>
            <strong>LLM Response</strong>
            <span class="token-count">
                {{ pyview.subject.prompt_tokens }}&nbsp;↑&nbsp;/&nbsp;{{ pyview.subject.completion_tokens }}&nbsp;↓
            </span>
            <button class="log-btn" onclick="pyview.toggle_raw()">
                {{ '▲' if not pyview.is_hidden else '▼' }} raw
            </button>
        </div>
        <div class="message-content {{ 'hidden' if pyview.is_hidden else '' }}">
            <pre class="log-pre">{{ pyview.subject.data }}</pre>
        </div>
    """

    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'style="order: {int(self.subject.created_at.timestamp())}"'

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_hidden = True

    def toggle_raw(self):
        self.is_hidden = not self.is_hidden
        self.update()