from __future__ import annotations
from typing import TYPE_CHECKING

from server.models.enums.task_enums import TaskCallStatusDetail
from ui.lib.model_view import ModelView
if TYPE_CHECKING:
    from server.models.tasks.agent_task_call import AgentTaskCall
    from ui.main.chat.messages.assistant_message import AssistantMessageView

class ToolCard(ModelView):
    DOM_ELEMENT_CLASS = "msg-row tool-card-row"
    TEMPLATE_STR = '''
        <div class="tool-card {% if pyview.subject.status_detail == 'HALTED_APPROVAL' %}open approval-pending{% endif %}  {% if pyview.is_open %}open{% endif %}">
        <div class="tool-card-header" onclick="pyview.toggle()">
            
            <span class="tool-card-icon">
                <svg width="14px" height="14px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            </span>
            <span class="tool-card-name">{{pyview.subject.task_definition_version.task_definition.name}}</span>
            {% if pyview.subject.status_detail == "HALTED_APPROVAL" %}
                <span class="tool-card-approval-hint">approval needed</span>
            {% else %}
                <span class="tool-card-preview">{"status": "{{pyview.subject.status}}, {{pyview.subject.status_detail}}", "message1": "", "path1":</span>
            {% endif %}
            <span class="query-card-status {{ pyview.subject.status|lower }}">{{ pyview.subject.status }}</span>

            <span class="tool-card-toggle">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><polyline points="9 18 15 12 9 6"></polyline></svg>
            </span>
        </div>
        {% if pyview.is_open %}
            <div class="tool-card-detail">
                <div class="tool-card-args">
                    {% for tool_arg_name, tool_arg_value in pyview.subject._resolve_call_arguments().items() %}
                        <div>
                            <span class="tool-arg-key">{{tool_arg_name}}</span> 
                            <span class="tool-arg-val">{{tool_arg_value}}</span>
                        </div>
                    {% endfor %}
                </div>
                <div class="tool-card-result"><pre>{{pyview.subject.get_result(allow_partial_results=True)}}</pre></div>
                {% if pyview.subject.status_detail == "HALTED_APPROVAL" %}
                    <div class="tool-card-approval">
                        <button class="tool-card-approve" onclick="pyview.approve_call()">Approve</button>
                        <button class="tool-card-deny" onclick="pyview.deny_call()">Deny</button>
                    </div>
                {% endif %}
            </div>
        {% endif %}
        </div>
    ''' 
    def __init__(self, subject:AgentTaskCall, parent: AssistantMessageView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_open = False

    def toggle(self):
        self.is_open = not self.is_open
        
        self.update()

    def approve_call(self) -> None:
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler.approve_taskcall(self.subject.pk)

    def deny_call(self) -> None:
        from runtime.tasks.call_fsm import TaskCallStateMachine
        TaskCallStateMachine.cancel(self.subject.pk, TaskCallStatusDetail.HALTED_APPROVAL)

