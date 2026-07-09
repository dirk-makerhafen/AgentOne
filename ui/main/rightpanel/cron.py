from __future__ import annotations
from typing import TYPE_CHECKING
from django.utils import timezone
from server.models.cron import Cronjob
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


CRON_ICONS = {
    "schedule": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    "history":  '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/><path d="M12 2v4"/><path d="M2 12h4"/></svg>',
}


class RightPanelCronSchedule(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Schedule</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            <div class="settings-card" style="margin-bottom:8px">
                <div class="detail-row">
                    <div class="detail-row-label">Expression</div>
                    <div class="detail-row-value"><code>{{ pyview.cron.schedule }}</code></div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Active</div>
                    <div class="detail-row-value">
                        {% if pyview.cron.is_active %}
                            <span style="color:var(--success)">yes</span>
                        {% else %}
                            <span style="color:var(--error)">paused</span>
                        {% endif %}
                    </div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Last run</div>
                    <div class="detail-row-value">{{ pyview.last_run }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Next run</div>
                    <div class="detail-row-value">{{ pyview.next_run }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Run count</div>
                    <div class="detail-row-value">{{ pyview.cron.run_count }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Agent</div>
                    <div class="detail-row-value">{{ pyview.cron.agent.name }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Workspace</div>
                    <div class="detail-row-value">{% if pyview.cron.workspace %}{{ pyview.cron.workspace.name }}{% else %}&mdash;{% endif %}</div>
                </div>
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def cron(self) -> Cronjob | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, Cronjob) else None

    @property
    def last_run(self) -> str:
        c = self.cron
        if c and c.last_run_at:
            return c.last_run_at.strftime("%Y-%m-%d %H:%M")
        return "\u2014"

    @property
    def next_run(self) -> str:
        c = self.cron
        if c and c.next_run:
            return c.next_run.strftime("%Y-%m-%d %H:%M")
        return "\u2014"


class RightPanelCronHistory(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>History</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% if pyview.entries %}
                {% for entry in pyview.entries %}
                <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 2px;font-size:12px;border-bottom:1px solid var(--border,.05)">
                    <span class="detail-badge {{ entry.badge }}" style="font-size:10px;padding:1px 6px">{{ entry.status }}</span>
                    <span style="color:var(--muted);font-size:11px">{{ entry.since }}</span>
                </div>
                {% endfor %}
            {% else %}
                <div style="font-size:12px;color:var(--muted);padding:8px">No executions yet.</div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def cron(self) -> Cronjob | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, Cronjob) else None

    @property
    def entries(self) -> list[dict]:
        c = self.cron
        if not c:
            return []
        from datetime import datetime, timezone as dt_timezone
        from server.models.tasks.agent_task_call import AgentTaskCall
        now = timezone.now()
        qs = AgentTaskCall.objects.filter(
            cronjob=c,
        ).order_by("-pk")[:20]
        rows = []
        for call in qs:
            dt = call.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=dt_timezone.utc)
            diff = now - dt
            secs = int(diff.total_seconds())
            if secs < 5:
                since = "just now"
            elif secs < 60:
                since = f"{secs}s ago"
            elif secs < 3600:
                since = f"{secs // 60}m ago"
            elif secs < 86400:
                since = f"{secs // 3600}h ago"
            else:
                since = f"{secs // 86400}d ago"
            badge = ""
            if call.status == "ENDED":
                badge = "ok"
            elif call.status == "ACTIVE":
                badge = "running"
            elif call.status == "WAITING":
                badge = "warn"
            elif call.status == "HALTED":
                badge = "err"
            rows.append({"status": call.status, "badge": badge, "since": since})
        return rows
