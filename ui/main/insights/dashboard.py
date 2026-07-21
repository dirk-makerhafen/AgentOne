"""Dashboard view — overview stats for the agent framework plus filterable inspect results."""
from __future__ import annotations

import json
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
from server.models.tasks.task_definition import TaskDefinition
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.lib.observableList import ObservableList
from ui.lib.pyHtmlGui.pyhtmlgui.view.observable_list_view import ObservableListView

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

INSPECT_STATUS_OPTIONS = [
    ("", "All"),
    ("ENDED", "Ended"),
    ("ACTIVE", "Active"),
    ("WAITING", "Waiting"),
    ("HALTED", "Halted"),
    ("NEW", "New"),
]


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


# ---------------------------------------------------------------------------
# Inspect result count — updates independently from the dashboard
# ---------------------------------------------------------------------------


class ResultCountView(ModelView):
    TEMPLATE_STR = """
    {{pyview.parent.result_count}} Items
    """


# ---------------------------------------------------------------------------
# Inspect row — expandable filterable result row
# ---------------------------------------------------------------------------


class InspectRowView(ModelView):
    TEMPLATE_STR = """
        <div class="inspect-row">
            <div class="inspect-row-content" onclick="pyview.toggle()">
                <span class="inspect-row-toggle">{{ pyview._toggle_marker }}</span>
                <span class="inspect-row-col--id">#{{ pyview.subject.pk }}</span>
                <span class="inspect-row-col--agent">{{ pyview.subject.session_version.agent.name if pyview.subject.session_version and pyview.subject.session_version.agent else "?" }}</span>
                <span class="inspect-row-col--task">{{ pyview.subject.task_definition.name if pyview.subject.task_definition else "?" }}</span>
                <span class="inspect-row-col--session">{{ pyview.subject.session.name if pyview.subject.session else "?" }}</span>
                <span class="inspect-row-col--status"><span class="detail-badge {{ pyview.STATUS_BADGE.get(pyview.subject.status, "") }}">{{ pyview.subject.status }}</span></span>
                <span class="inspect-row-col--time">{{ pyview._timesince(pyview.subject.created_at) }}</span>
            </div>
            {% if pyview._expanded %}
                <div id="inspect_detail_{{pyview.uid}}" class="inspect-row-detail">
                    <div class="inspect-detail-grid">
                        <span class="inspect-detail-label">Status detail</span>
                        <span>{{ pyview.subject.status_detail }}</span>
                        {% if pyview.subject.ended_at %}
                        <span class="inspect-detail-label">Ended at</span>
                        <span>{{ pyview.subject.ended_at.strftime("%Y-%m-%d %H:%M:%S") if pyview.subject.ended_at else "" }}</span>
                        {% endif %}
                        {% if pyview.subject.retry_count %}
                        <span class="inspect-detail-label">Retries</span>
                        <span>{{ pyview.subject.retry_count }}</span>
                        {% endif %}
                        <span class="inspect-detail-label">Session</span>
                        <span><a href="#" class="inspect-detail-link" onclick="pyview._dashboard_view.open_session({{ pyview.subject.session_id }});return false">{{ pyview.subject.session.name if pyview.subject.session else "?" }}</a></span>
                    </div>
                    <div class="inspect-section">
                        <div class="inspect-section-header">Result</div>
                        <pre class="inspect-code-block">{{ pyview.subject.get_result(timeout= 0, recursive = True, allow_partial_results = True) }}</pre>
                    </div>
                    {% if pyview.subject.carguments_json %}
                    <div class="inspect-section">
                        <div class="inspect-section-header">Arguments</div>
                        <pre class="inspect-code-block">{{ pyview.subject.carguments_json }}</pre>
                    </div>
                    {% endif %}
                </div>
            {% endif %}
        </div>
    """

    def __init__(self, subject, parent, dashboard_view=None, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._dashboard_view = dashboard_view
        self._expanded = False
        self.STATUS_BADGE = {
            "ENDED": "ok",
            "ACTIVE": "running",
            "WAITING": "warn",
            "HALTED": "err",
            "NEW": "",
        }

    def _load_result(self):
        self._result = self.subject.get_result(timeout=0, recursive=True, allow_partial_results=True)

    @property
    def task_result(self):
        self._load_result()
        return json.dumps(self._result, indent=2, default=str) if self._result else None

    @property
    def task_arguments(self):
        if self.subject.carguments_json:
            return json.dumps(self.subject.carguments_json, indent=2, default=str)
        return None

    @property
    def _toggle_marker(self) -> str:
        return "\u25bc" if self._expanded else "\u25b6"

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self.update()

    def _timesince(self, dt: datetime | None) -> str:
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


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


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

                <div class="inspect-filters">
                        <input id="inspect_agent_{{pyview.uid}}" class="inspect-filter-input" type="text" placeholder="Filter by agent..." value="{{ pyview._agent_filter }}" spellcheck="false" autocomplete="off" oninput="pyview.apply_filters(this.value,document.getElementById('inspect_status_{{pyview.uid}}').value,document.getElementById('inspect_task_{{pyview.uid}}').value,document.getElementById('inspect_session_{{pyview.uid}}').value)">
                        <select id="inspect_status_{{pyview.uid}}" class="inspect-filter-select" onchange="pyview.apply_filters(document.getElementById('inspect_agent_{{pyview.uid}}').value,this.value,document.getElementById('inspect_task_{{pyview.uid}}').value,document.getElementById('inspect_session_{{pyview.uid}}').value)">
                            {% for val, label in pyview.status_options %}
                            <option value="{{ val }}"{% if pyview._status_filter == val %} selected{% endif %}>{{ label }}</option>
                            {% endfor %}
                        </select>
                        <input id="inspect_task_{{pyview.uid}}" class="inspect-filter-input" type="text" placeholder="Filter by task..." value="{{ pyview._task_filter }}" spellcheck="false" autocomplete="off" oninput="pyview.apply_filters(document.getElementById('inspect_agent_{{pyview.uid}}').value,document.getElementById('inspect_status_{{pyview.uid}}').value,this.value,document.getElementById('inspect_session_{{pyview.uid}}').value)">
                        <input id="inspect_session_{{pyview.uid}}" class="inspect-filter-input" type="text" placeholder="Session #..." value="{{ pyview._session_filter }}" spellcheck="false" autocomplete="off" oninput="pyview.apply_filters(document.getElementById('inspect_agent_{{pyview.uid}}').value,document.getElementById('inspect_status_{{pyview.uid}}').value,document.getElementById('inspect_task_{{pyview.uid}}').value,this.value)">
                        <span class="inspect-filter-label">{{ pyview.result_count_view.render() }}</span>
                    </div>

                    <div class="inspect-results">
                        <div class="inspect-results-header">
                            <span class="inspect-row-col--id">Call</span>
                            <span class="inspect-row-col--fill">Agent</span>
                            <span class="inspect-row-col--fill">Task</span>
                            <span class="inspect-row-col--fill">Session</span>
                            <span class="inspect-row-col--status">Status</span>
                            <span class="inspect-row-col--time">When</span>
                        </div>
                        {{ pyview.results_view.render() }}
                    </div>

            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.status_options = INSPECT_STATUS_OPTIONS
        self._agent_filter = ""
        self._status_filter = ""
        self._task_filter = ""
        self._session_filter = ""
        self.result_count_view = ResultCountView(self.subject, self)
        self.results_list = ObservableList()
        self.results_view = ObservableListView(
            subject=self.results_list,
            parent=self,
            item_class=InspectRowView,
            dom_element_class="",
            dashboard_view=self,
        )
        self._rebuild_results()

    # ------------------------------------------------------------------
    # Metrics
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
    # Inspect filters
    # ------------------------------------------------------------------

    def apply_filters(self, agent: str = "", status: str = "", task: str = "", session: str = "") -> None:
        self._agent_filter = agent.strip()
        self._status_filter = status.strip()
        self._task_filter = task.strip()
        self._session_filter = session.strip()
        self._rebuild_results()
        self.result_count_view.update()

    # ------------------------------------------------------------------
    # Inspect results
    # ------------------------------------------------------------------

    def _build_qs(self):
        qs = AgentTaskCall.objects.select_related(
            "task_definition",
            "session",
            "session_version__agent",
            "taskcall_result_run",
        ).order_by("-pk")

        if self._agent_filter:
            qs = qs.filter(session_version__agent__name__icontains=self._agent_filter)
        if self._status_filter:
            qs = qs.filter(status=self._status_filter)
        if self._task_filter:
            qs = qs.filter(task_definition__name__icontains=self._task_filter)
        if self._session_filter:
            try:
                session_pk = int(self._session_filter)
                qs = qs.filter(session__pk=session_pk)
            except ValueError:
                qs = qs.filter(session__name__icontains=self._session_filter)
        return qs

    @property
    def result_count(self) -> int:
        return self._build_qs().count()

    def _rebuild_results(self) -> None:
        self.results_list.clear()
        for c in self._build_qs()[:200]:
            self.results_list.append(c)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def open_session(self, session_pk: int) -> None:
        from ui.main.chat.chat import Chat
        try:
            session = SessionModel.objects.get(pk=session_pk)
        except SessionModel.DoesNotExist:
            return
        self.parent.create_and_open_tab(Chat, session)

    def refresh(self) -> None:
        self._rebuild_results()
