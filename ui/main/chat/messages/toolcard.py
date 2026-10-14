from __future__ import annotations
from typing import TYPE_CHECKING

from server.models.enums.task_enums import TaskCallStatusDetail
from ui.lib.model_view import ModelView
if TYPE_CHECKING:
    from server.models.tasks.agent_task_call import AgentTaskCall
    from ui.main.chat.messages.assistant_message import AssistantMessageView

def _fmt_duration(seconds: float | None) -> str:
    """Format a duration in seconds as a compact human string."""
    if seconds is None:
        return ""
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return ""
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m {int(seconds % 60):02d}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60:02d}m"


def _fmt_clock(value) -> str:
    """Format a datetime as HH:MM:SS (empty string when missing)."""
    if value is None:
        return ""
    try:
        return value.strftime("%H:%M:%S")
    except Exception:
        return ""


class ToolCard(ModelView):
    DOM_ELEMENT_CLASS = "msg-row tool-card-row"
    TEMPLATE_STR = '''
        <div class="tool-card {% if pyview.subject.status_detail == 'HALTED_APPROVAL' %}open approval-pending{% endif %}  {% if pyview.is_open %}open{% endif %}">
        <div class="tool-card-header" onclick="pyview.toggle()">

            <span class="card-icon">
                <svg width="14px" height="14px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="display:inline-block;vertical-align:-0.15em;flex-shrink:0"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            </span>
            <span class="card-title">{{pyview.tool_name}}</span>
            {% if pyview.subject.status_detail == "HALTED_APPROVAL" %}
                <span class="tool-card-approval-hint">approval needed</span>
            {% else %}
                <span class="card-sub">{{pyview.status_label}}</span>
            {% endif %}
            <span class="card-meta" title="Last update: {{pyview.subject.updated_at}}">{{pyview.updated_str}}</span>
            {% if pyview.show_duration %}
                <span class="card-meta" title="Time the tool took so far / in total">{{pyview.duration_str}}</span>
            {% endif %}
            <span class="card-status {{ pyview.status_class }}">{{ pyview.subject.status }}</span>

            <span class="card-toggle">
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
                        <input id="tool_feedback_{{ pyview.subject.pk }}" type="text" placeholder="Reason for denying (optional)" autocomplete="off" spellcheck="false">
                        <button class="tool-card-approve" onclick="pyview.approve_call()">Approve</button>
                        <button class="tool-card-deny" onclick="pyview.deny_call(document.getElementById('tool_feedback_{{ pyview.subject.pk }}').value)">Deny</button>
                    </div>
                {% endif %}
            </div>
        {% endif %}
        </div>
    ''' 
    @property
    def tool_name(self) -> str:
        """Display name of the invoked tool (never raises in templates)."""
        try:
            tdv = getattr(self.subject, "task_definition_version", None)
            td = getattr(tdv, "task_definition", None) if tdv is not None else None
            if td is not None and getattr(td, "name", None):
                return td.name
            td = getattr(self.subject, "task_definition", None)
            if td is not None and getattr(td, "name", None):
                return td.name
        except Exception:
            pass
        return f"call #{getattr(self.subject, 'pk', '?')}"

    @property
    def status_label(self) -> str:
        """Human-readable status detail label (e.g. 'Running')."""
        try:
            detail = getattr(self.subject, "status_detail", "") or ""
            labels = dict(TaskCallStatusDetail.choices)
            return labels.get(detail, detail or getattr(self.subject, "status", ""))
        except Exception:
            return getattr(self.subject, "status", "")

    @property
    def status_class(self) -> str:
        """CSS modifier for the status pill (success/failure/active/waiting)."""
        try:
            detail = (getattr(self.subject, "status_detail", "") or "").upper()
            if "SUCCESS" in detail:
                return "success"
            if "FAILURE" in detail or "CANCELLED" in detail or "STOPPED" in detail:
                return "failure"
            status = (getattr(self.subject, "status", "") or "").lower()
            if status in ("success", "failure", "active", "waiting"):
                return status
            if status == "halted":
                return "waiting"
            if status == "ended":
                return "waiting"
            return status or "waiting"
        except Exception:
            return "waiting"

    @property
    def updated_str(self) -> str:
        try:
            return _fmt_clock(self.subject.updated_at)
        except Exception:
            return ""

    @property
    def show_duration(self) -> bool:
        """Show the elapsed/total time once the tool started or finished."""
        try:
            if getattr(self.subject, "ended_at", None) is not None:
                return True
            return (getattr(self.subject, "status", "") or "") in ("ACTIVE", "HALTED", "ENDED")
        except Exception:
            return False

    @property
    def duration_str(self) -> str:
        try:
            start = getattr(self.subject, "created_at", None)
            end = getattr(self.subject, "ended_at", None) or getattr(self.subject, "updated_at", None)
            if start is None or end is None:
                return ""
            return _fmt_duration((end - start).total_seconds())
        except Exception:
            return ""

    def __init__(self, subject:AgentTaskCall, parent: AssistantMessageView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.is_open = False

    def toggle(self):
        self.is_open = not self.is_open
        
        self.update()

    def approve_call(self) -> None:
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler.approve_taskcall(self.subject.pk)

    def deny_call(self, feedback: str = "") -> None:
        from runtime.tasks.call_scheduler import CallScheduler
        CallScheduler.deny_taskcall(self.subject.pk, feedback=feedback)

