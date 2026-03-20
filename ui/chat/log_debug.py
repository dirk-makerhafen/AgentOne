from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView


class DebugLogView(PyHtmlView):
    DOM_ELEMENT_CLASS = 'DebugLogView conversation-log-item log-type-debug debug-log-item'
    TEMPLATE_STR = """
        <div class="message-header">
            <strong>[{{ pyview.subject.created_at }}]</strong> <strong>Debug Log</strong>
            <button class="btn btn-xs btn-default log-btn" onclick="pyview.toggle_details()"><i class="fa fa-plus"></i> More </button>
        </div>
        <div class="debug-log-full message-content {{ 'hidden' if pyview.is_details_hidden else '' }}">
            <pre>s:{{ pyview.subject }}</pre>
        </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject
        self.is_details_hidden = True

    def toggle_details(self):
        self.is_details_hidden = not self.is_details_hidden
        self.update()

    @property
    def DOM_ELEMENT_EXTRAS(self):
        return f'style="order: {int(self.subject.created_at.timestamp())}"'
    