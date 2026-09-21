"""Cron overview — last active scheduled jobs at a glance.

Shown when the cron sidebar icon is clicked (previously the main content
stayed on whatever tab was open, since cron had no main page).
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


def cron_row_data(job) -> dict:
    """Row info dict for a cron job (no raise)."""
    try:
        agent_name = getattr(getattr(job, "agent", None), "name", "") or ""
    except Exception:
        agent_name = ""
    try:
        if getattr(job, "is_archived", False):
            status = "archived"
        elif getattr(job, "is_active", False):
            status = "active"
        else:
            status = "paused"
    except Exception:
        status = ""
    def _fmt(dt) -> str:
        if not dt:
            return "—"
        try:
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(dt)

    return {
        "pk": job.pk,
        "name": getattr(job, "name", "") or f"Job {job.pk}",
        "schedule": getattr(job, "schedule", "") or "",
        "agent_name": agent_name,
        "status": status,
        "last_run_at": _fmt(getattr(job, "last_run_at", None)),
        "next_run_at": _fmt(getattr(job, "next_run_at", None)),
        "total_runs": getattr(job, "total_runs", 0) or 0,
    }


class CronOverview(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="ws-ov-topbar">
            <div class="ws-ov-breadcrumb">
                <span class="ws-ov-crumb">Scheduled jobs</span>
            </div>
            <div class="ws-ov-search">
                <svg class="ws-ov-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                <input id="cronOvSearch" placeholder="Search jobs..." oninput="cronOvFilter()" autocomplete="off">
            </div>
            <button class="ws-ov-primary" onclick="pyview.openCreate()">＋ New job</button>
        </div>
        <div class="main-view-body">
            <div class="main-view-content ws-ov-content">
                <div class="ws-ov-heading-row">
                    <div>
                        <h1 class="ws-ov-title">Scheduled jobs</h1>
                        <div class="ws-ov-subtitle">{{ pyview.jobs|length }} job(s), most recently active first</div>
                    </div>
                </div>
                {% if pyview.jobs %}
                <table class="insights-table" id="cronOvTable">
                    <thead><tr>
                        <th>Job</th>
                        <th>Schedule</th>
                        <th>Agent</th>
                        <th>Status</th>
                        <th>Last run</th>
                        <th>Next run</th>
                        <th class="num">Runs</th>
                    </tr></thead>
                    <tbody>
                    {% for job in pyview.jobs %}
                    <tr class="clickable" data-name="{{ job.name|lower }}" onclick="pyview.openJob({{ job.pk }})">
                        <td><strong>{{ job.name }}</strong></td>
                        <td class="muted">{{ job.schedule }}</td>
                        <td>{{ job.agent_name }}</td>
                        <td>{% if job.status == "active" %}<span class="key-badge key-ok">active</span>{% elif job.status == "paused" %}<span class="key-badge key-builtin">paused</span>{% else %}<span class="key-badge key-missing">archived</span>{% endif %}</td>
                        <td class="muted">{{ job.last_run_at }}</td>
                        <td class="muted">{{ job.next_run_at }}</td>
                        <td class="num">{{ job.total_runs }}</td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <div class="ws-ov-empty" style="display:block">
                    <div class="ws-ov-empty-icon">⌕</div>
                    <h2>No scheduled jobs found</h2>
                    <div>Create a new job to run agents on a schedule.</div>
                </div>
                {% endif %}
            </div>
        </div>
        <script>
            function cronOvFilter() {
                var q = document.getElementById("cronOvSearch").value.toLowerCase();
                var rows = document.querySelectorAll("#cronOvTable tbody tr");
                for (var i = 0; i < rows.length; i++) {
                    var match = (rows[i].dataset.name || "").indexOf(q) !== -1;
                    rows[i].style.display = match ? "" : "none";
                }
            }
        </script>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def jobs(self) -> list[dict]:
        from server.models.cron import Cronjob

        try:
            all_jobs = list(
                Cronjob.objects.all()
                .select_related("agent")
                .order_by("-is_active", "-last_run_at")
            )
        except Exception:
            return []
        return [cron_row_data(j) for j in all_jobs]

    def openJob(self, pk: int) -> None:
        from server.models.cron import Cronjob
        from ui.main.cron.cron import CronView

        try:
            job = Cronjob.objects.get(pk=int(pk))
        except (Cronjob.DoesNotExist, ValueError, TypeError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(CronView, job)

    def openCreate(self) -> None:
        from ui.main.cron.create import CronCreateView

        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(CronCreateView, self.subject)

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent
