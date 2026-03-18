from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView

class InterAgentLogView(PyHtmlView):
    TEMPLATE_STR = """
    <div id="inter_agent_message_{{ pyview.subject.id }}" class="conversation-log-item log-type-debug inter-agent-message-item">
        <div class="message-header">
            <strong>[{{ pyview.subject.created_at }}]</strong> <strong>Inter-Agent Message : </strong>
            <button class="btn btn-xs btn-default log-btn" onclick="pyview.toggle_details()"><i class="fa fa-plus"></i> More </button>
        </div>
        <div id="inter_agent_message_full_{{ pyview.subject.id }}" class="message-content {{ 'hidden' if pyview.is_details_hidden else '' }}">
            <pre>{{ pyview.subject.data }}</pre>
        </div>
    </div>
    """
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_details_hidden = True

    def toggle_details(self):
        self.is_details_hidden = not self.is_details_hidden
        self.update()
