from threading import Lock
import types
import typing

from django.db.models.query import QuerySet
from server.models.agents.agent_instance import AgentInstance




class ChatView(PyHtmlView):
    DOM_ELEMENT_CLASS = "resizable-container"
    DOM_ELEMENT_EXTRAS =  'data-orientation="vertical"'
    TEMPLATE_STR = """
        <div id="logArea_{{ pyview.subject.id }}" class="logArea resizable-panel conversation-log flex-column" data-size-pc="80">
            <div id="agent-status-ribbon_{{ pyview.subject.id }}" class="agent-status-ribbon agent-status-ribbon-hidden">
                <span class="status-text"></span>
            </div>
            {{ pyview.message_views.render() }}
        </div>
                    
        <div class="resizable-panel flex-row" data-size-pc="20" style="justify-content: end;">
            <div class="chat_user_input">
                <div id="messageInput_{{ pyview.subject.id }}" class="rich-text-input" contenteditable="true" data-placeholder="Enter your message..."></div>
            </div>
            <div class="chat-actions">
                <button id="sendMessageBtn_{{ pyview.subject.id }}" class="submit_button btn btn-success" type="submit" onclick="pyview.send_message(document.getElementById('messageInput_{{ pyview.subject.id }}').innerText)">Send</button>
            </div>

        </div>
        <script>
            parent = document.getElementById("{{pyview.uid}}");
            initializeSplitForContainer(parent.parentNode);
            /*pa rent.par nt.querySelectorAll('.resizable-container').forEach(container => {
                initializeSplitForContainer(container);
            });*/
        </script>
    """
    def __init__(self, subject: AgentInstance, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.f = subject
        print("subject.agent_task_calls", subject.agent_task_calls.all())
        self.s = [
            [ subject.conversation_messages, MessageView],
            [ subject.queries, QueryView],
            [ subject.responses, ResponseView],
            [ subject.debug_log_entries, DebugLogView ],
            [ subject.agent_task_calls.order_by("-created_at")[:10], TaskCallView ]
        ]
        print("HEHHEHRHERER", subject.agent_task_calls.all())
        self.message_views = QuerySetsView(subject=self.s, parent=self)


    def send_message(self, message):
        if message.strip():
            self.subject.latest_agent_instance_version.get_runtime_instance().add_user_message.delay(message=message)
        self.update()