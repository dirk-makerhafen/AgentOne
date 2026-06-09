"""Dashboard view — overview stats for the agent framework."""
from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import TYPE_CHECKING

from django.db.models import Count
from django.utils import timezone

from server.models.agents.agent import AgentModel
from server.models.collections import DataCollection
from server.models.cron import Cronjob
from server.models.message import Message
from server.models.sessions.session import SessionModel
from server.models.tasks.agent_task_call import AgentTaskCall
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


STATUS_META = {
    "ENDED": ("Ended", "ok"),
    "ACTIVE": ("Active", "running"),
    "WAITING": ("Waiting", "warn"),
    "HALTED": ("Halted", "err"),
    "NEW": ("New", ""),
}

STATUS_ORDER = ["ENDED", "ACTIVE", "WAITING", "HALTED", "NEW"]

STATUS_COLORS = {
    "ok": "var(--success)",
    "running": "var(--info)",
    "warn": "var(--warning)",
    "err": "var(--error)",
}

ITEM_BADGE = {
    "ENDED": "ok",
    "ACTIVE": "running",
    "WAITING": "warn",
    "HALTED": "err",
    "NEW": "",
}

METRIC_ICONS = {
    "agents": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>',
    "sessions": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>',
    "taskcalls": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>',
    "dataflows": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 4v16h16"></path><path d="M4 12h16"></path><path d="M12 4v16"></path></svg>',
    "cron": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>',
    "messages": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="4" y1="9" x2="20" y2="9"></line><line x1="4" y1="15" x2="20" y2="15"></line><line x1="10" y1="3" x2="8" y2="21"></line><line x1="16" y1="3" x2="14" y2="21"></line></svg>',
}


def _timesince(dt: datetime | None) -> str:
    if not dt:
        return ""
    now = timezone.now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)
    diff = now - dt
    secs = int(diff.total_seconds())
    if secs < 5:
        return "just now"
    if secs < 60:
        return f"{secs}s ago"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


class DashboardView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">Dashboard</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Refresh" onclick="pyview.refresh()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content" style="max-width:1200px">

                <div class="insights-grid">
                    {% for m in pyview.all_metrics %}
                    <div class="insights-stat">
                        <div class="insights-stat-icon">{{ m.icon|safe }}</div>
                        <div class="insights-stat-info">
                            <div class="insights-stat-value">{{ m.value }}</div>
                            <div class="insights-stat-label">{{ m.label }}</div>
                        </div>
                    </div>
                    {% endfor %}
                </div>

                <div class="system-health-metrics">
                    <div class="system-health-metric" data-system-health-metric="cpu">
                        <div class="system-health-label"><span>CPU</span><span class="system-health-value" data-system-health-value="" title="0%">0%</span></div>
                        <div class="system-health-bar" role="progressbar" aria-label="CPU usage" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="system-health-bar-fill" style="width: 0%;"></div></div>
                    </div>
                    <div class="system-health-metric" data-system-health-metric="memory">
                        <div class="system-health-label"><span>RAM</span><span class="system-health-value" data-system-health-value="" title="0%">0%</span></div>
                        <div class="system-health-bar" role="progressbar" aria-label="RAM usage" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="system-health-bar-fill" style="width: 0%;"></div></div>
                    </div>
                    <div class="system-health-metric" data-system-health-metric="disk">
                        <div class="system-health-label"><span>Disk</span><span class="system-health-value" data-system-health-value="" title="--">&mdash;</span></div>
                        <div class="system-health-bar" role="progressbar" aria-label="Disk usage" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="system-health-bar-fill" style="width: 0%;"></div></div>
                    </div>
                </div>

                <div class="insights-row">
                    <div class="insights-card">
                        <div class="insights-card-title">Token Breakdown</div>
                        <div class="insights-token-row">
                            <span class="insights-token-label">Input</span>
                            <span class="insights-token-value">--</span>
                        </div>
                        <div class="insights-token-row">
                            <span class="insights-token-label">Output</span>
                            <span class="insights-token-value">--</span>
                        </div>
                        <div class="insights-token-row insights-token-total">
                            <span class="insights-token-label">Total</span>
                            <span class="insights-token-value">--</span>
                        </div>
                    </div>

                    <div class="insights-card">
                        <div class="insights-card-title">Task call status</div>
                        {% for row in pyview.status_rows %}
                        <div class="insights-bar-row" style="margin-bottom:4px">
                            <span class="insights-bar-label">{{ row.label }}</span>
                            <div class="insights-bar-track">
                                <div class="insights-bar-fill{% if row.pct >= 80 %} peak{% endif %}" style="width:{{ row.pct }}%;background:{{ row.color }}"></div>
                            </div>
                            <span class="insights-bar-value">{{ row.count }}</span>
                        </div>
                        {% endfor %}
                    </div>
                </div>

                <div class="insights-card">
                    <div class="insights-card-title">
                        Recent activity
                        <span style="font-weight:400;text-transform:none;letter-spacing:0;margin-left:8px;font-size:11px;color:var(--muted)">last 10 calls</span>
                    </div>
                    {% if pyview.recent_rows %}
                        {% for call in pyview.recent_rows %}
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 2px;font-size:12px;border-bottom:1px solid var(--border,.05)">
                            <div style="display:flex;align-items:center;gap:6px;min-width:0">
                                <span class="detail-badge {{ call.badge }}" style="font-size:10px;padding:1px 6px">{{ call.status }}</span>
                                <span style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ call.name }}</span>
                            </div>
                            <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
                                <span style="color:var(--muted);font-size:11px">#{{ call.pk }}</span>
                                <span style="color:var(--muted);font-size:11px">{{ call.since }}</span>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="insights-empty">No task calls yet.</div>
                    {% endif %}
                </div>

            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)

    # ------------------------------------------------------------------
    # All metrics
    # ------------------------------------------------------------------

    @property
    def all_metrics(self) -> list[dict]:
        return [
            {"label": "Agents",    "value": AgentModel.objects.count(),    "icon": METRIC_ICONS["agents"]},
            {"label": "Sessions",  "value": SessionModel.objects.count(),  "icon": METRIC_ICONS["sessions"]},
            {"label": "Task calls","value": AgentTaskCall.objects.count(), "icon": METRIC_ICONS["taskcalls"]},
            {"label": "Data flows","value": DataCollection.objects.count(), "icon": METRIC_ICONS["dataflows"]},
            {"label": "Cron jobs", "value": Cronjob.objects.count(),       "icon": METRIC_ICONS["cron"]},
            {"label": "Messages",  "value": Message.objects.count(),       "icon": METRIC_ICONS["messages"]},
        ]

    # ------------------------------------------------------------------
    # Status breakdown
    # ------------------------------------------------------------------

    @property
    def status_rows(self) -> list[dict]:
        qs = (
            AgentTaskCall.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        seen = {row["status"]: row["count"] for row in qs}
        total = max(sum(seen.values()), 1)
        rows = []
        for s in STATUS_ORDER:
            count = seen.get(s, 0)
            label, cls = STATUS_META.get(s, (s, ""))
            rows.append({
                "label": label,
                "count": count,
                "cls": cls,
                "pct": round(count / total * 100, 1),
                "color": STATUS_COLORS.get(cls, "var(--muted)"),
            })
        return rows

    # ------------------------------------------------------------------
    # Recent activity
    # ------------------------------------------------------------------

    @property
    def recent_rows(self) -> list[dict]:
        calls = AgentTaskCall.objects.select_related("task_definition").order_by("-pk")[:10]
        rows = []
        for c in calls:
            rows.append({
                "pk": c.pk,
                "status": c.status,
                "badge": ITEM_BADGE.get(c.status, ""),
                "name": c.task_definition.name if c.task_definition else "?",
                "since": _timesince(c.created_at),
            })
        return rows

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        self.update()
