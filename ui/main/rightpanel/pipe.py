from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.pipe import NamedPipe
from server.models.tasks.agent_task_call import AgentTaskCall
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


PIPE_ICONS = {
    "activity": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    "subscribers": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
}


class RightPanelPipeActivity(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Activity</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% if pyview.entries %}
                {% for entry in pyview.entries %}
                <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 2px;font-size:12px;border-bottom:1px solid var(--border,.05)">
                    <span class="detail-badge {{ entry.badge }}" style="font-size:10px;padding:1px 6px">{{ entry.status }}</span>
                    <span style="color:var(--muted);font-size:11px">{{ entry.since }}</span>
                </div>
                {% endfor %}
            {% else %}
                <div style="font-size:12px;color:var(--muted);padding:8px">No recent activity.</div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def pipe(self) -> NamedPipe | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, NamedPipe) else None

    @property
    def entries(self) -> list[dict]:
        p = self.pipe
        if not p:
            return []
        from datetime import datetime, timezone as dt_timezone
        from django.utils import timezone
        now = timezone.now()
        qs = AgentTaskCall.objects.filter(
            pipe_output_names__contains=p.name,
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


class RightPanelPipeSubscribers(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Subscribers</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% if pyview.subscribers %}
                {% for sub in pyview.subscribers %}
                <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 2px;font-size:12px;border-bottom:1px solid var(--border,.05)">
                    <span style="font-weight:500">{{ sub.name }}</span>
                    <span>
                        {% if sub.is_active %}
                            <span style="color:var(--success);font-size:11px">active</span>
                        {% else %}
                            <span style="color:var(--muted);font-size:11px">paused</span>
                        {% endif %}
                    </span>
                </div>
                {% endfor %}
            {% else %}
                <div style="font-size:12px;color:var(--muted);padding:8px">No subscribers.</div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def pipe(self) -> NamedPipe | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, NamedPipe) else None

    @property
    def subscribers(self) -> list:
        p = self.pipe
        if not p:
            return []
        return list(p.subscriptions.all().order_by("name"))
