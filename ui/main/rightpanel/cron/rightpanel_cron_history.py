from __future__ import annotations
from typing import TYPE_CHECKING
from django.utils import timezone
from server.models.cron import Cronjob
from ui.lib.model_view import ModelView


if TYPE_CHECKING:
    from ui.main.rightpanel.cron.rightpanel_cron import RightPanelCron
    from ui.app import UiApp



class RightPanelCronHistory(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
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

    def __init__(self, subject: Cronjob, parent: RightPanelCron, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def entries(self) -> list[dict]:
        c = self.subject
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

