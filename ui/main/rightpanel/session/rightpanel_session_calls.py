from __future__ import annotations
from typing import TYPE_CHECKING, Any
from collections import defaultdict
from django.utils import timezone
from server.models.sessions.session import SessionModel
from server.models.tasks.agent_task_call import AgentTaskCall
from server.models.enums.task_enums import TaskCallStatusDetail, TaskCallStatus
from ui.lib.model_view import ModelView


if TYPE_CHECKING:
    from ui.main.rightpanel.session.rightpanel_session import RightPanelSession
    from ui.app import UiApp


STATUS_COLORS = {
    TaskCallStatusDetail.NEW: "var(--muted)",
    TaskCallStatusDetail.WAITING_QUEUE: "var(--link)",
    TaskCallStatusDetail.WAITING_RETRY: "var(--warning)",
    TaskCallStatusDetail.WAITING_DEPENDENCY: "var(--link)",
    TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS: "var(--link)",
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
    TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS: "waiting",
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

_ACTIVE_DETAILS = {
    TaskCallStatusDetail.ACTIVE_QUEUED,
    TaskCallStatusDetail.ACTIVE_RUNNING,
    TaskCallStatusDetail.WAITING_QUEUE,
    TaskCallStatusDetail.WAITING_RETRY,
    TaskCallStatusDetail.WAITING_DEPENDENCY,
    TaskCallStatusDetail.WAITING_SUBTASKS_OR_HOOKS,
    TaskCallStatusDetail.WAITING_RATELIMIT,
}


class CallNodeView(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "task-call-item"
    TEMPLATE_STR = """
        {% if pyview.has_children %}
        <span class="session-tree-caret" onclick="event.stopPropagation();this.classList.toggle('collapsed');var n=this.parentElement.nextElementSibling;var d={{ pyview.depth }};while(n&&parseInt(n.dataset.depth)>d){n.style.display=this.classList.contains('collapsed')?'none':'';n=n.nextElementSibling;}" aria-hidden="true">&#9660;</span>
        {% endif %}
        <div style="flex:1;min-width:min-content">
            <div style="font-size:12px;font-weight:500;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ pyview.subject.task_definition.name }}:{{pyview.subject.pk}}</div>
            <div style="font-size:10px;color:var(--muted);margin-top:1px">{{ pyview.time_label }}</div>
        </div>
        {% if pyview.is_active %}
        <span class="session-state-indicator is-streaming" style="visibility:visible;flex-shrink:0;width:8px;height:8px"></span>
        {% endif %}
        <span class="task-call-badge" style="background:{{ pyview.status_color }}">{{ pyview.status_label }}</span>
        {% if not pyview.subject.status == "ENDED" %}
        <button class="panel-icon-btn" onclick="pyview.cancel()" title="Cancel task call" style="flex-shrink:0;margin-left:4px;color:var(--danger);font-size:12px;padding:2px 4px;border:none;background:none;cursor:pointer">✕</button>
        {% endif %}
    """

    def __init__(self, subject: AgentTaskCall, parent: ModelView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.depth = kwargs.get("depth", 0)
        self.has_children = kwargs.get("has_children", False)
        self.DOM_ELEMENT_EXTRAS = 'style="margin-left:{}em" data-depth="{}"'.format(self.depth, self.depth)

    @property
    def time_label(self) -> str:
        if self.subject.created_at:
            return self.subject.created_at.strftime("%H:%M:%S")
        return ""

    @property
    def is_active(self) -> bool:
        return self.subject.status_detail in _ACTIVE_DETAILS

    @property
    def status_color(self) -> str:
        return STATUS_COLORS.get(self.subject.status_detail, "var(--muted)")

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.subject.status_detail, str(self.subject.status_detail))

    def cancel(self) -> None:
        """Cancel/stop this task call and propagate to dependents."""
        from server.models.tasks.agent_task_call import AgentTaskCall as ATC
        from server.tasks.recovery_scheduler import _force_end_call

        call = ATC.objects.get(pk=self.subject.pk)
        _force_end_call(call)
        self.parent.refresh()

    def extra_html_attributes(self) -> str:
        return 'style="margin-left:{}em" data-depth="{}"'.format(self.depth, self.depth)



class RightPanelSessionCalls(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
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

            {% for item in pyview._items %}
                {{ item.render() }}
            {% endfor %}
        </div>
    '''

    def __init__(self, subject: SessionModel, parent: RightPanelSession, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._items: list[CallNodeView] = []

    @property
    def active_count(self) -> int:
        from django.db.models import F as _F
        s = self.session
        if s is None:
            return 0
        # Count non-ended calls under the newest root task for the session
        root = AgentTaskCall.objects.filter(
            session=s.model,
            session_root_task=_F("pk"),
        ).order_by("-created_at").first()
        if not root:
            return 0
        return AgentTaskCall.objects.filter(
            session_root_task=root,
        ).exclude(status=TaskCallStatus.ENDED).count()

    @property
    def session(self):
        return self.parent.current_session

    def refresh(self):
        self._rebuild()
        self.update()

    def _rebuild(self):
        for item in self._items:
            item.delete(remove_from_dom=False)
        self._items = []
        s = self.session
        if s is not None and s.model:
            self._items = self._build_flat_items(s.model, self)


    def _build_flat_items(self, session_model, parent_view: ModelView) -> list[CallNodeView]:
        from django.db.models import F as _F

        MAX_SIBLINGS = 1000
        MAX_DEPTH = 100

        # Find the newest root call for this session via session_root_task.
        # Root calls have session_root_task pointing to themselves.
        root_call = AgentTaskCall.objects.filter(
            session=session_model,
            session_root_task=_F("pk"),
        ).order_by("-created_at").first()
        if not root_call:
            return []

        # Fetch only calls under this root (current turn's call tree).
        calls = list(AgentTaskCall.objects.filter(
            session_root_task=root_call,
        ).select_related(
            "task_definition",
            "parent_taskrun__agent_task_call",
        ).order_by("-created_at")[:500])

        # Build tree using parent_taskrun.agent_task_call_id (multi-level nesting).
        call_map = {c.pk: c for c in calls}
        child_ids: dict[int, list[int]] = defaultdict(list)
        roots: list[int] = []

        for c in calls:
            parent_call_id = None
            if c.parent_taskrun and c.parent_taskrun.agent_task_call_id in call_map:
                parent_call_id = c.parent_taskrun.agent_task_call_id
                child_ids[parent_call_id].append(c.pk)
            else:
                roots.append(c.pk)

        inserted: set[int] = set()
        flat_items: list[CallNodeView] = []

        def _walk(call_id: int, depth: int = 0) -> None:
            if depth > MAX_DEPTH or call_id in inserted:
                return
            call = call_map.get(call_id)
            if not call:
                return
            inserted.add(call_id)
            children = child_ids.get(call_id, [])[:MAX_SIBLINGS]
            node = CallNodeView(
                subject=call,
                parent=parent_view,
                depth=depth,
                has_children=bool(children),
            )
            flat_items.append(node)
            for ccid in children:
                _walk(ccid, depth + 1)

        for rid in roots:
            _walk(rid)

        return flat_items
