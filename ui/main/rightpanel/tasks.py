from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.enums.task_enums import TaskCallStatusDetail
from ui.lib.model_view import ModelView
from ui.lib.queryset_view import QuerySetView

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


STATUS_COLORS = {
    TaskCallStatusDetail.NEW: "var(--muted)",
    TaskCallStatusDetail.WAITING_QUEUE: "var(--link)",
    TaskCallStatusDetail.WAITING_RETRY: "var(--warning)",
    TaskCallStatusDetail.WAITING_DEPENDENCY: "var(--link)",
    TaskCallStatusDetail.WAITING_SUBTASK: "var(--link)",
    TaskCallStatusDetail.WAITING_RATELIMIT: "var(--warning)",
    TaskCallStatusDetail.ACTIVE_QUEUED: "var(--accent)",
    TaskCallStatusDetail.ACTIVE_RUNNING: "var(--accent)",
    TaskCallStatusDetail.HALTED_INPUT: "var(--warning)",
    TaskCallStatusDetail.HALTED_APPROVAL: "#f59e0b",
    TaskCallStatusDetail.HALTED_STAGNATED: "var(--danger)",
    TaskCallStatusDetail.HALTED_PAUSED: "var(--muted)",
    TaskCallStatusDetail.ENDED_SUCCESS: "var(--success)",
    TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION: "var(--danger)",
    TaskCallStatusDetail.ENDED_FAILURE_LOGIC: "var(--danger)",
    TaskCallStatusDetail.ENDED_CANCELLED: "var(--muted)",
    TaskCallStatusDetail.ENDED_STOPPED: "var(--muted)",
}

STATUS_LABELS = {
    TaskCallStatusDetail.NEW: "new",
    TaskCallStatusDetail.WAITING_QUEUE: "queued",
    TaskCallStatusDetail.WAITING_RETRY: "retry",
    TaskCallStatusDetail.WAITING_DEPENDENCY: "waiting",
    TaskCallStatusDetail.WAITING_SUBTASK: "waiting",
    TaskCallStatusDetail.WAITING_RATELIMIT: "rate-limited",
    TaskCallStatusDetail.ACTIVE_QUEUED: "active",
    TaskCallStatusDetail.ACTIVE_RUNNING: "running",
    TaskCallStatusDetail.HALTED_INPUT: "needs input",
    TaskCallStatusDetail.HALTED_APPROVAL: "needs approval",
    TaskCallStatusDetail.HALTED_STAGNATED: "stagnated",
    TaskCallStatusDetail.HALTED_PAUSED: "paused",
    TaskCallStatusDetail.ENDED_SUCCESS: "done",
    TaskCallStatusDetail.ENDED_FAILURE_EXCEPTION: "failed",
    TaskCallStatusDetail.ENDED_FAILURE_LOGIC: "failed",
    TaskCallStatusDetail.ENDED_CANCELLED: "cancelled",
    TaskCallStatusDetail.ENDED_STOPPED: "stopped",
}


class TaskCallItem(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "task-call-item"
    TEMPLATE_STR = """
        <div style="flex:1;min-width:0">
            <div style="font-size:12px;font-weight:500;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ pyview.subject.task_definition.name }}</div>
            <div style="font-size:10px;color:var(--muted);margin-top:1px">{{ pyview.created_label }}</div>
        </div>
        <span class="task-call-badge" style="background:{{ pyview.status_color }}">{{ pyview.status_label }}</span>
    """

    @property
    def created_label(self) -> str:
        if self.subject.created_at:
            return self.subject.created_at.strftime("%H:%M:%S")
        return ""

    @property
    def status_color(self) -> str:
        return STATUS_COLORS.get(self.subject.status_detail, "var(--muted)")

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.subject.status_detail, str(self.subject.status_detail))


class RightPanelTasks(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="panel-header">
            <span>Task Calls</span>
            <div class="panel-actions">
                <button class="panel-icon-btn" onclick="pyview.refresh()" title="Refresh">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
                </button>
            </div>
        </div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% if pyview.active_count %}
            <div style="font-size:10px;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:0.5px;margin:0 0 6px">{{ pyview.active_count }} active</div>
            {% endif %}
            {{ pyview.call_list.render() }}
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.call_list = QuerySetView(
            subject=AgentTaskCall.objects.none(),
            parent=self,
            item_class=TaskCallItem,
            dom_element="div",
            dom_element_class="task-call-list",
        )
        self._rebuild()

    @property
    def active_count(self) -> int:
        s = self.session
        if s is None:
            return 0
        from server.models.enums.task_enums import TaskCallStatus
        return AgentTaskCall.objects.filter(session=s.model).exclude(status=TaskCallStatus.ENDED).count()

    @property
    def session(self):
        return self.parent.current_session

    def refresh(self):
        self._rebuild()
        self.update()

    def _rebuild(self):
        s = self.session
        if s is not None:
            from server.models.enums.task_enums import TaskCallStatus
            qs = AgentTaskCall.objects.filter(
                session=s.model,
            ).exclude(
                status=TaskCallStatus.ENDED,
            ).select_related(
                "task_definition",
            ).order_by("-created_at")[:50]
        else:
            qs = AgentTaskCall.objects.none()
        self.call_list.query = qs
        self.call_list._recreate()