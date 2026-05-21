from __future__ import annotations
from ui.lib.pyHtmlGui.pyhtmlgui.pyhtmlgui_instance import PyHtmlGuiInstance
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.tasks.agent_task_run import AgentTaskRun
from ui.lib.model_view import ModelView
from server.models.sessions.session import SessionModel
from ui.lib.multi_queryset_view import MultiQuerySetView
from ui.chat.message import MessageView
from ui.chat.query import QueryView
from ui.chat.response import ResponseView
from ui.chat.log_debug import DebugLogView
from ui.chat.log_fs import FilesystemLogView
from ui.chat.task_call import TaskCallView
import unicodedata

from ui.old.instance.task_trace_view import TaskTraceView


class ChatWorkspaceView(ModelView):
    DOM_ELEMENT_CLASS = "ChatWorkspaceView resizable-container"
    DOM_ELEMENT_EXTRAS = 'data-orientation="vertical"'
    TEMPLATE_STR = """
       
        {{ pyview.task_trace_view.render() w}}

        <div class="chat-timeline resizable-panel flex-column" data-size-pc="80">
            <div class="chat-mode-bar">
                <button class="chat-mode-btn {{ 'active' if pyview.detail_level == 'simple'    else '' }}" onclick="pyview.set_detail_level('simple')">Chat</button>
                <button class="chat-mode-btn {{ 'active' if pyview.detail_level == 'developer' else '' }}" onclick="pyview.set_detail_level('developer')">Developer</button>
            </div>
            <div class="chat-scroll">
                {{ pyview.timeline.render() }}
                <div id="timeline" style="position:relative; width:100%; height:600px; border:1px solid #ccc;"></div>
            </div>
        </div>
        <div class="chat-input-panel resizable-panel flex-row" data-size-pc="20">
            <div class="chat-input-wrap">
                <div id="messageInput_{{ pyview.subject.id }}"
                     class="chat-input"
                     contenteditable="true"
                     data-placeholder="Enter your message…"></div>
            </div>
            <div class="chat-send-wrap">
                <button class="btn btn-success chat-send-btn"
                        onclick="pyview.send_message(document.getElementById('messageInput_{{ pyview.subject.id }}').innerText)">
                    Send
                </button>
            </div>
        </div>
        <script>
            (function() {
                var el = document.getElementById("{{ pyview.uid }}");
                if (el && el.parentNode) initializeSplitForContainer(el.parentNode);
            })();
            $(".chat-scroll").scrollTop($(".chat-scroll")[0].scrollHeight);
        </script>
    """

    def __init__(self, subject: SessionModel, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.s = subject
        self.detail_level = 'simple'
        self.timeline = None
        self._build_timeline()


    def _build_timeline(self):
        if self.timeline is not None:
            self.timeline.delete(remove_from_dom=False)

        instance = self.subject
        latest = instance.latest_session_version


        self.task_trace_view = TaskTraceView(subject=self.subject, parent=self)

        from server.models.tasks.agent_task_run import AgentTaskRun as _Run
        _child_ids = list(_Run.objects.filter(session_version__agent_instance=instance).values_list('child_taskcalls', flat=True)) \
            + list(_Run.objects.filter(session_version__agent_instance=instance).values_list('taskrun_result_references', flat=True))
        _child_ids = [x for x in _child_ids if x is not None]
        root_calls = []# instance.agent_task_calls.exclude(id__in=_child_ids).order_by('-created_at')[:50]
        
        if self.detail_level == 'simple':
            querysets = [(instance.conversation_messages.order_by('created_at'), MessageView)]
        else:
            # Root calls only — children appear recursively inside TaskRunView.
            # A root call is any call NOT referenced as a subtask or result-ref
            # by any TaskRun belonging to this instance.
 
            querysets = [
                (instance.conversation_messages.order_by('created_at'), MessageView),
                (instance.queries.order_by('created_at'),               QueryView),
                (instance.responses.order_by('created_at'),             ResponseView),
                (root_calls,                                            TaskCallView),
            ]
            try:
                from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
                querysets.append((
                    FsLogEntry.objects.filter(session_version=latest).order_by('created_at')
                    if latest else FsLogEntry.objects.none(),
                    FilesystemLogView,
                ))
            except Exception:
                pass
            try:
                from server.models.debug_log_entry import DebugLogEntry
                querysets.append((
                    DebugLogEntry.objects.filter(session=self.subject).order_by('created_at'),
                    DebugLogView,
                ))
            except Exception:
                pass

        self.timeline = MultiQuerySetView(
            subject=querysets,
            parent=self,
            sort_key=lambda w: w.subject.created_at.timestamp(),
        )

    def set_detail_level(self, level: str):
        if level not in ('simple', 'developer'):
            return
        self.detail_level = level
        self._build_timeline()
        self.update()

    def send_message(self, message: str):
        message = unicodedata.normalize("NFKC", message)
        if message.strip():
            self.subject.get_runtime().process_chat_message(message_string=message)
        self.update()