from __future__ import annotations
from typing import TYPE_CHECKING
from django.utils import timezone
from server.models.cron import Cronjob
from ui.lib.model_view import ModelView, orm_subscribe


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
                    <span style="display:flex;align-items:center;gap:6px">
                        <span style="color:var(--muted);font-size:11px">{{ entry.since }}</span>
                        {% if entry.can_cancel %}
                        <button class="panel-icon-btn" onclick="pyview.cancelCall({{ entry.pk }})" title="Cancel run" aria-label="Cancel run" style="flex-shrink:0;color:var(--danger);font-size:12px;padding:2px 4px;border:none;background:none;cursor:pointer">✕</button>
                        {% endif %}
                    </span>
                </div>
                {% endfor %}
            {% else %}
                <div style="font-size:12px;color:var(--muted);padding:8px">No executions yet.</div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: Cronjob, parent: RightPanelCron, **kwargs):
        super().__init__(subject, parent, **kwargs)
        if getattr(subject, "pk", None):
            # Calls for this cron job publish on AgentTaskCall.cronjob:<pk>,
            # so status changes re-render the history without a tab switch.
            orm_subscribe(self, subject.observables.calls, self.on_orm_updated)

    def cancelCall(self, call_pk: int) -> None:
        """Cancel/stop one waiting or active run of this cron job."""
        from server.models.tasks.agent_task_call import AgentTaskCall
        from server.tasks.recovery_scheduler import _force_end_call

        try:
            call = AgentTaskCall.objects.get(pk=call_pk, cronjob=self.subject)
        except (AgentTaskCall.DoesNotExist, TypeError, ValueError):
            self.update()
            return
        if call.status != "ENDED":
            _force_end_call(call)
        self.update()

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
            rows.append({
                "pk": call.pk,
                "status": call.status,
                "badge": badge,
                "since": since,
                "can_cancel": call.status != "ENDED",
            })
        return rows

