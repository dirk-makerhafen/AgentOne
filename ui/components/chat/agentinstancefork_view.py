from ui.pyHtmlGui.pyhtmlgui.view.pyhtmlview import PyHtmlView


class AgentInstanceForkView(PyHtmlView):
    TEMPLATE_STR = """
    <div id="agent_fork_message_{{ pyview.subject.id }}" class="conversation-log-item log-type-agent-fork agent-fork-message" onclick="pyview.toggle_details()">
        <div class="message-header">
            <strong>[{{ pyview.subject.created_at }}]</strong> <strong>System:</strong> Agent Forked
        </div>
        <div class="message-content">
            <p>Agent Instance <strong>{{ pyview.subject.parent_instance_id }}</strong> forked a new instance: <strong>{{ pyview.subject.child_instance_id }}</strong></p>
            <div id="agent_fork_details_{{ pyview.subject.id }}" class="agent-fork-details {{ 'hidden' if pyview.is_details_hidden else '' }}">
                <p>Parent Instance ID: {{ pyview.subject.parent_instance_id }}</p>
                <p>Child Instance ID: {{ pyview.subject.child_instance_id }}</p>
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
