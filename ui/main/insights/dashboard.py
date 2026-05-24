"""Dashboard view — overview stats for the agent framework."""
from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import TYPE_CHECKING

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from server.models.agents.agent import AgentModel
from server.models.cron import Cronjob
from server.models.message import Message
from server.models.pipe import NamedPipe, NamedPipeSubscription
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

                <div class="system-health-metrics">
                    {% for m in pyview.metrics_row1 %}
                    <div class="detail-card" style="text-align:center">
                        <div class="detail-card-title" style="margin-bottom:4px">{{ m.label }}</div>
                        <div style="font-size:28px;font-weight:700;line-height:1.2">{{ m.value }}</div>
                    </div>
                    {% endfor %}
                </div>

                <div style="height:12px"></div>

                <div class="system-health-metrics">
                    {% for m in pyview.metrics_row2 %}
                    <div class="detail-card" style="text-align:center">
                        <div class="detail-card-title" style="margin-bottom:4px">{{ m.label }}</div>
                        <div style="font-size:28px;font-weight:700;line-height:1.2">{{ m.value }}</div>
                    </div>
                    {% endfor %}
                </div>

                <div style="display:flex;gap:16px;margin-top:16px;flex-wrap:wrap">

                    <div class="detail-card" style="flex:1;min-width:280px">
                        <div class="detail-card-title">Task call status</div>
                        {% for row in pyview.status_rows %}
                        <div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px">
                            <span class="detail-badge {{ row.cls }}" style="min-width:60px;text-align:center">{{ row.label }}</span>
                            <div style="flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden">
                                <div style="width:{{ row.pct }}%;height:100%;background:{{ row.color }};border-radius:4px;transition:width .3s"></div>
                            </div>
                            <span style="font-weight:600;min-width:32px;text-align:right">{{ row.count }}</span>
                        </div>
                        {% endfor %}
                    </div>

                    <div class="detail-card" style="flex:2;min-width:360px">
                        <div class="detail-card-title">
                            Recent activity
                            <span style="font-weight:400;text-transform:none;letter-spacing:0;margin-left:8px;font-size:11px;color:var(--muted)">last 10 calls</span>
                        </div>
                        {% if pyview.recent_rows %}
                            {% for call in pyview.recent_rows %}
                            <div class="detail-row" style="padding:6px 2px;font-size:12px">
                                <div style="display:flex;justify-content:space-between;align-items:center;width:100%">
                                    <div style="display:flex;align-items:center;gap:6px;min-width:0">
                                        <span class="detail-badge {{ call.badge }}" style="font-size:10px;padding:1px 6px">{{ call.status }}</span>
                                        <span style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ call.name }}</span>
                                    </div>
                                    <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
                                        <span style="color:var(--muted);font-size:11px">#{{ call.pk }}</span>
                                        <span style="color:var(--muted);font-size:11px">{{ call.since }}</span>
                                    </div>
                                </div>
                            </div>
                            {% endfor %}
                        {% else %}
                            <div style="padding:12px;color:var(--muted);text-align:center;font-size:12px">
                                No task calls yet.
                            </div>
                        {% endif %}
                    </div>

                </div>

            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)

    # ------------------------------------------------------------------
    # Metric rows
    # ------------------------------------------------------------------

    @property
    def metrics_row1(self) -> list[dict]:
        return [
            {"label": "Agents",    "value": AgentModel.objects.count()},
            {"label": "Sessions",  "value": SessionModel.objects.count()},
            {"label": "Task calls","value": AgentTaskCall.objects.count()},
        ]

    @property
    def metrics_row2(self) -> list[dict]:
        return [
            {"label": "Pipes",     "value": NamedPipe.objects.count()},
            {"label": "Cron jobs", "value": Cronjob.objects.count()},
            {"label": "Messages",  "value": Message.objects.count()},
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
