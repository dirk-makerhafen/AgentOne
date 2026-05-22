from __future__ import annotations
from ui.lib.model_view import ModelView


class FilesystemLogView(ModelView):
    DOM_ELEMENT_CLASS = "FilesystemLogView conversation-log-item log-type-fs"

    TEMPLATE_STR = """
        <div class="message-header">
            <span class="message-time">{{ pyview.subject.created_at.strftime('%H:%M:%S') }}</span>
            <strong>FS {{ pyview.subject.action }}</strong>
            <span class="fs-log-path">{{ pyview.subject.path }}</span>
            <button class="log-btn" onclick="pyview.toggle_details()">
                {{ '▲' if not pyview.is_hidden else '▼' }} details
            </button>
        </div>
        <div class="message-content {{ 'hidden' if pyview.is_hidden else '' }}">
            <pre class="log-pre">{{ pyview.subject.data }}</pre>
        </div>
    """

    CSS_STR = """
        .fs-log-path {
            font-family: var(--font-mono);
            font-size: 0.82em;
            color: var(--text-muted);
            flex-grow: 1;
            overflow: hidden;
            white-space: nowrap;
            text-overflow: ellipsis;
        }
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