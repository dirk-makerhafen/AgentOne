from ui.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView



class FilesystemLogView(PyHtmlView):
    TEMPLATE_STR = """
    <div id="filesystem_message_{{ pyview.subject.id }}" class="conversation-log-item log-type-fs filesystem-log-item">
        <div class="message-header">
            <strong>[{{ pyview.subject.created_at }}]</strong> <strong>FS {{ pyview.subject.action }}:</strong> {{ pyview.subject.path }}
            <button class="btn btn-xs btn-default log-btn" onclick="pyview.toggle_details()"><i class="fa fa-plus"></i> Details </button>
        </div>
        <div class="message-content">
            <div id="filesystem_full_{{ pyview.subject.id }}" class="filesystem-content {{ 'hidden' if pyview.is_details_hidden else '' }}">
                <pre>{{ pyview.subject.data }}</pre>
            </div>
        </div>
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_details_hidden = True

    def toggle_details(self):
        self.is_details_hidden = not self.is_details_hidden
        self.update()
