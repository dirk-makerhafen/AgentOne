from __future__ import annotations
from ui.lib.model_view import ModelView


class DebugLogView(ModelView):
    DOM_ELEMENT_CLASS = "DebugLogView conversation-log-item log-type-debug"

    TEMPLATE_STR = """
        <div class="message-header">
            <span class="message-time">{{ pyview.subject.created_at.strftime('%H:%M:%S') }}</span>
            <strong>Debug</strong>
            <button class="log-btn" onclick="pyview.toggle_details()">
                {{ '▲' if not pyview.is_hidden else '▼' }} more
            </button>
        </div>
        <div class="message-content {{ 'hidden' if pyview.is_hidden else '' }}">
            <pre class="log-pre">{{ pyview.subject }}</pre>
        </div>
    """

    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'style="order: {int(self.subject.created_at.timestamp())}"'

    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_hidden = True

    def toggle_details(self):
        self.is_hidden = not self.is_hidden
        self.update()