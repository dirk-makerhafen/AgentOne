from __future__ import annotations
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail, TaskRunStatus
 
 
# Maps status detail values to (css_modifier, display_label) pairs.
# css_modifier is appended to a base class e.g. "badge--success"
_CALL_DETAIL_MAP: dict[str, tuple[str, str]] = {
    TaskCallStatusDetail.NEW:                    ("neutral",  "new"),
    TaskCallStatusDetail.WAITING_QUEUE:          ("waiting",  "queued"),
    TaskCallStatusDetail.WAITING_DEPENDENCY:     ("waiting",  "waiting"),
    TaskCallStatusDetail.WAITING_RETRY:          ("waiting",  "retry"),
    TaskCallStatusDetail.WAITING_SUBTASK:        ("waiting",  "subtask"),
    TaskCallStatusDetail.WAITING_RATELIMIT:      ("warning",  "rate limited"),
    TaskCallStatusDetail.ACTIVE_QUEUED:          ("active",   "queued"),
    TaskCallStatusDetail.ACTIVE_RUNNING:         ("active",   "running"),
    TaskCallStatusDetail.HALTED_INPUT:           ("halted",   "awaiting input"),
    TaskCallStatusDetail.HALTED_APPROVAL:        ("halted",   "approval needed"),
    TaskCallStatusDetail.HALTED_STAGNATED:       ("halted",   "step limit"),
    TaskCallStatusDetail.HALTED_PAUSED:          ("halted",   "paused"),
    TaskCallStatusDetail.ENDED_SUCCESS:          ("success",  "done"),
    TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION:("error",    "failed"),
    TaskCallStatusDetail.ENDED_FAILURE_LOGIC:    ("error",    "logic error"),
    TaskCallStatusDetail.ENDED_CANCELLED:        ("neutral",  "cancelled"),
    TaskCallStatusDetail.ENDED_STOPPED:          ("neutral",  "stopped"),
}
 
_RUN_STATUS_MAP: dict[str, tuple[str, str]] = {
    TaskRunStatus.NEW:                 ("neutral",  "new"),
    TaskRunStatus.QUEUED:              ("waiting",  "queued"),
    TaskRunStatus.ACTIVE:              ("active",   "running"),
    TaskRunStatus.WAITING_RESULTTASKS: ("waiting",  "waiting"),
    TaskRunStatus.RATE_LIMITED:        ("warning",  "rate limited"),
    TaskRunStatus.SUCCESS:             ("success",  "done"),
    TaskRunStatus.FAILURE:             ("error",    "failed"),
}
 
 
class StatusBadgeView(ModelView):
    """
    Renders a small status pill for a TaskCall or TaskRun status.
 
    Usage — inline in a parent template:
        {{ pyview.status_badge.render() }}
 
    Or instantiate directly with a status string:
        StatusBadgeView(subject=task_call, parent=self)
 
    The subject can be an AgentTaskCall or AgentTaskRun instance.
    The badge automatically picks the right label and CSS modifier.
    """
    DOM_ELEMENT = "span"
    TEMPLATE_STR = """<span class="badge badge--{{ pyview.modifier }}">{{ pyview.label }}</span>"""
 
    def __init__(self, subject, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
 
    @property
    def modifier(self) -> str:
        return self._resolve()[0]
 
    @property
    def label(self) -> str:
        return self._resolve()[1]
 
    def _resolve(self) -> tuple[str, str]:
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.models.tasks.agent_task_run import AgentTaskRun
        if isinstance(self.subject, AgentTaskCall):
            return _CALL_DETAIL_MAP.get(
                self.subject.status_detail, ("neutral", self.subject.status_detail)
            )
        if isinstance(self.subject, AgentTaskRun):
            return _RUN_STATUS_MAP.get(
                self.subject.status, ("neutral", self.subject.status)
            )
        # Fallback: subject is a raw status string
        s = str(self.subject)
        return _CALL_DETAIL_MAP.get(s) or _RUN_STATUS_MAP.get(s, ("neutral", s))