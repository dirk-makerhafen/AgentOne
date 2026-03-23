from __future__ import annotations
from ui.lib.model_view import ModelView
from server.models.agents.agent_instance import AgentInstance
from ui.lib.multi_queryset_view import MultiQuerySetView
from ui.chat.message import MessageView
from ui.chat.query import QueryView
from ui.chat.response import ResponseView
from ui.chat.log_debug import DebugLogView
from ui.chat.log_fs import FilesystemLogView
from ui.chat.task_call import TaskCallView


class ChatWorkspaceView(ModelView):
    DOM_ELEMENT_CLASS = "ChatWorkspaceView resizable-container"
    DOM_ELEMENT_EXTRAS = 'data-orientation="vertical"'
    TEMPLATE_STR = """
        <div class="chat-timeline resizable-panel flex-column" data-size-pc="80">
            <div class="chat-mode-bar">
                <button class="chat-mode-btn {{ 'active' if pyview.detail_level == 'simple' else '' }}"
                        onclick="pyview.set_detail_level('simple')">Chat</button>
                <button class="chat-mode-btn {{ 'active' if pyview.detail_level == 'developer' else '' }}"
                        onclick="pyview.set_detail_level('developer')">Developer</button>
            </div>
            <div class="chat-scroll">
                {{ pyview.timeline.render() }}
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
        </script>
    """

    CSS_STR = """
/* Timeline scroll area */
.chat-timeline { overflow: hidden; background: var(--bg); }

.chat-mode-bar {
    display: flex;
    gap: 4px;
    padding: 4px 8px;
    background: var(--bg-subtle);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
}
.chat-mode-btn {
    padding: 2px 10px;
    font-size: 0.8em;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
}
.chat-mode-btn.active             { background: var(--accent); border-color: var(--accent); color: #fff; }
.chat-mode-btn:not(.active):hover { background: var(--bg-raised); }

.chat-scroll {
    flex-grow: 1;
    overflow-y: auto;
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

/* Input panel */
.chat-input-panel {
    border-top: 1px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
    padding: 8px;
    gap: 8px;
    align-items: flex-end;
}
.chat-input-wrap {
    flex-grow: 1;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--bg);
    overflow: hidden;
    transition: border-color 0.15s;
}
.chat-input-wrap:focus-within { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(37,99,235,.1); }
.chat-input {
    width: 100%;
    min-height: 60px;
    max-height: 200px;
    overflow-y: auto;
    padding: 8px 12px;
    font-family: var(--font-sans);
    font-size: 0.95em;
    outline: none;
    line-height: 1.5;
}
.chat-input:empty::before { content: attr(data-placeholder); color: var(--text-faint); pointer-events: none; }
.chat-input img { max-width: 90%; max-height: 140px; border-radius: var(--r-sm); border: 1px solid var(--border); margin: 4px; vertical-align: middle; }
.chat-send-wrap { flex-shrink: 0; }
.chat-send-btn  { padding: 8px 16px; }

/* Log item base */
.conversation-log-item {
    border-radius: var(--r-md);
    width: 100%;
    box-shadow: var(--shadow-sm);
    animation: chat-fade-in 0.15s ease-in;
    overflow: hidden;
}
@keyframes chat-fade-in { from { opacity: 0; } to { opacity: 1; } }

.conversation-log-item .message-header {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding: 4px 10px;
    font-size: 0.8em;
    color: var(--text-muted);
    border-bottom: 1px solid rgba(0,0,0,.04);
}
.conversation-log-item .message-content { padding: 6px 10px; font-size: 0.92em; line-height: 1.55; }
.message-actions { display: flex; gap: 8px; margin-left: auto; }
.message-actions .pin-icon,
.message-actions .hide-icon { cursor: pointer; color: var(--text-faint); transition: color 0.15s; }
.message-actions .pin-icon.pinned { color: var(--accent); }
.message-actions .hide-icon.hide_from_context { color: var(--text); }

/* Item type colouring */
.log-type-conversation { background: var(--bg); border: 1px solid var(--border-light); }
.log-type-llm   { background: #f8f9ff; border: 1px solid #dde3f0; }
.log-type-fs    { background: #f6fdf7; border: 1px solid #c8e6c9; }
.log-type-debug { background: var(--bg-subtle); border: 1px solid var(--border-light); }

/* Action buttons inside message headers */
.log-btn {
    padding: 1px 6px;
    font-size: 0.75em;
    border-radius: 4px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: background 0.1s, color 0.1s;
    white-space: nowrap;
}
.log-btn:hover { background: var(--accent); border-color: var(--accent); color: #fff; }

/* Log filtering via class on .chat-scroll */
.chat-scroll.hide-conversation .log-type-conversation { display: none; }
.chat-scroll.hide-llm          .log-type-llm          { display: none; }
.chat-scroll.hide-fs           .log-type-fs           { display: none; }
.chat-scroll.hide-debug        .log-type-debug        { display: none; }

/* Task call tree */
.task-node {
    border: 1px solid var(--border);
    border-radius: var(--r-sm);
    margin-bottom: 2px;
    background: var(--bg-subtle);
    border-left: 3px solid var(--accent);
    overflow: hidden;
}
.task-node-run  { border-left-color: var(--warning); }
.task-node.is-subtask { margin-left: 16px; }
.task-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    cursor: pointer;
    transition: background 0.1s;
}
.task-header:hover { background: var(--bg-raised); }
.task-icon  { width: 18px; color: var(--text-muted); font-size: 0.85em; flex-shrink: 0; }
.task-info  { flex-grow: 1; min-width: 0; }
.task-name  { font-size: 0.85em; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.task-id    { font-size: 0.75em; color: var(--text-faint); margin-left: 4px; }
.task-statusbadge {
    font-size: 0.72em;
    padding: 1px 6px;
    border-radius: 8px;
    background: var(--badge-neutral-bg);
    color: var(--badge-neutral-fg);
    margin-left: 6px;
    white-space: nowrap;
}
.status-ended-success .task-statusbadge                          { background: var(--badge-success-bg); color: var(--badge-success-fg); }
.status-ended-failure-exception .task-statusbadge,
.status-ended-failure-logic     .task-statusbadge                { background: var(--badge-error-bg);   color: var(--badge-error-fg); }
.status-active-running  .task-statusbadge                        { background: var(--badge-active-bg);  color: var(--badge-active-fg); font-weight:600; }
.status-waiting-ratelimit .task-statusbadge                      { background: var(--badge-warning-bg); color: var(--badge-warning-fg); }
.task-meta    { font-size: 0.75em; color: var(--text-faint); flex-shrink: 0; white-space: nowrap; }
.task-details { border-top: 1px solid var(--border-light); }
.task-children { padding-left: 12px; border-left: 1px solid var(--border-light); margin-left: 8px; }
.section-label { font-size: 0.7em; text-transform: uppercase; letter-spacing: .05em; color: var(--text-faint); padding: 3px 2px; }
.debug-json {
    font-family: var(--font-mono);
    font-size: 0.78em;
    background: #1e1e2e;
    color: #cdd6f4;
    padding: 8px 10px;
    border-radius: var(--r-sm);
    max-height: 180px;
    overflow-y: auto;
}
    """

    def __init__(self, subject: AgentInstance, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.detail_level = 'simple'
        self.timeline = None
        self._build_timeline()

    def _build_timeline(self):
        if self.timeline is not None:
            self.timeline.delete(remove_from_dom=False)

        instance = self.subject
        latest = instance.latest_agent_instance_version

        if self.detail_level == 'simple':
            querysets = [(instance.conversation_messages.order_by('created_at'), MessageView)]
        else:
            # Root calls only — children appear recursively inside TaskRunView.
            # A root call is any call NOT referenced as a subtask or result-ref
            # by any TaskRun belonging to this instance.
            from server.models.tasks.agent_task_run import AgentTaskRun as _Run
            _child_ids = list(
                _Run.objects.filter(agent_instance_version__agent_instance=instance)
                .values_list('taskrun_subtask_references', flat=True)
            ) + list(
                _Run.objects.filter(agent_instance_version__agent_instance=instance)
                .values_list('taskrun_result_references', flat=True)
            )
            _child_ids = [x for x in _child_ids if x is not None]
            root_calls = instance.agent_task_calls.exclude(
                id__in=_child_ids
            ).order_by('created_at')[:100]

            querysets = [
                (instance.conversation_messages.order_by('created_at'), MessageView),
                (instance.queries.order_by('created_at'),               QueryView),
                (instance.responses.order_by('created_at'),             ResponseView),
                (root_calls,                                             TaskCallView),
            ]
            try:
                from tools.builtin_filesystem.models.fs_log_entry import FsLogEntry
                querysets.append((
                    FsLogEntry.objects.filter(agent_instance_version=latest).order_by('created_at')
                    if latest else FsLogEntry.objects.none(),
                    FilesystemLogView,
                ))
            except Exception:
                pass
            try:
                from server.models.debug_log_entry import DebugLogEntry
                querysets.append((
                    DebugLogEntry.objects.filter(agent_instance=self.subject).order_by('created_at'),
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
        if message.strip():
            self.subject.latest_agent_instance_version \
                .get_runtime_instance() \
                .add_user_message.delay(message=message)
        self.update()