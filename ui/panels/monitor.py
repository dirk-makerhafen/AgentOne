from __future__ import annotations
from ui.lib.queryset_view import QuerySetView
from server.models.enums.task_enums import TaskCallStatus, TaskCallStatusDetail
from ui.lib.model_view import ModelView
from ui.lib.model_view import ModelView


class ActiveCallRowView(ModelView):
    """One row in the global task monitor — shows an active or halted call."""
    DOM_ELEMENT_CLASS = "ActiveCallRowView monitor-call-row"

    TEMPLATE_STR = """
        <div class="monitor-row status-{{ pyview.subject.status_detail|lower|replace('_','-') }}">
            <span class="monitor-agent text-muted small">
                {{ pyview.subject.agent_instance.agent.name }}
                i{{ pyview.subject.agent_instance.pk }}
            </span>
            <span class="monitor-task">
                {{ pyview.subject.agent_task_definition.name }}
                <span class="task-id">#{{ pyview.subject.id }}</span>
            </span>
            <span class="monitor-status badge">{{ pyview.subject.status_detail }}</span>
            <span class="monitor-time text-muted small">
                {{ pyview.subject.created_at.strftime('%H:%M:%S') }}
            </span>
            {% if pyview.subject.status_detail == "HALTED_APPROVAL" %}
                <button class="btn btn-xs btn-success" onclick="pyview.approve()">
                    Approve
                </button>
            {% endif %}
            {% if pyview.subject.status_detail == "WAITING_RATELIMIT" %}
                <span class="badge badge--warning">rate limited</span>
            {% endif %}
        </div>
    """

    def approve(self):
        from runtime.tasks.call_runtime import CallScheduler
        CallScheduler.approve_taskcall(self.subject.pk)
        self.update()


class MonitorPanelView(ModelView):
    """
    Global task monitor panel.
    Shows all non-ended task calls across all agents — active, halted, waiting.
    Useful for spotting stuck tasks, approving pending calls, and watching
    rate-limited calls queue up.
    """
    DOM_ELEMENT_CLASS = "MonitorPanelView"

    TEMPLATE_STR = """
        <div class="panel-section">
            <div class="panel-section-header">
                Active &amp; halted calls
                <button class="btn btn-xs btn-default" onclick="pyview.refresh()">
                    <i class="fa fa-refresh"></i>
                </button>
            </div>
            {{ pyview.active_calls_view.render() }}
        </div>

        <div class="panel-section">
            <div class="panel-section-header">Waiting (rate limited)</div>
            {{ pyview.rate_limited_calls_view.render() }}
        </div>

        <div class="panel-section">
            <div class="panel-section-header">Waiting for approval</div>
            {{ pyview.approval_calls_view.render() }}
        </div>
    """

    def __init__(self, subject, parent, **kwargs):
        """Subject is UiApp (the global Observable data model)."""
        super().__init__(subject, parent, **kwargs)
        from server.models.tasks.agent_task_call import AgentTaskCall

        self.active_calls_view = QuerySetView(
            subject=AgentTaskCall.objects.filter(
                status__in=[TaskCallStatus.ACTIVE, TaskCallStatus.WAITING]
            ).exclude(
                status_detail__in=[
                    TaskCallStatusDetail.WAITING_RATELIMIT,
                    TaskCallStatusDetail.HALTED_APPROVAL,
                ]
            ).order_by('-created_at')[:50],
            parent=self,
            item_class=ActiveCallRowView,
        )
        self.rate_limited_calls_view = QuerySetView(
            subject=AgentTaskCall.objects.filter(
                status_detail=TaskCallStatusDetail.WAITING_RATELIMIT
            ).order_by('created_at'),
            parent=self,
            item_class=ActiveCallRowView,
        )
        self.approval_calls_view = QuerySetView(
            subject=AgentTaskCall.objects.filter(
                status_detail=TaskCallStatusDetail.HALTED_APPROVAL
            ).order_by('created_at'),
            parent=self,
            item_class=ActiveCallRowView,
        )

    def refresh(self):
        self.update()