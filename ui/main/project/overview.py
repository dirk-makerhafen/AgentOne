"""Projects overview — last active projects at a glance.

Shown when the projects sidebar icon is clicked (previously the main
content stayed on whatever tab was open, since projects had no main page).
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


def project_card_data(project) -> dict:
    """Card info dict for a project (no raise)."""
    try:
        from server.models.agents.agent import AgentModel

        agent_count = AgentModel.objects.filter(parent_project=project).count()
    except Exception:
        agent_count = 0
    try:
        from server.models.sessions.session import SessionModel

        session_count = SessionModel.objects.filter(parent_project=project).count()
    except Exception:
        session_count = 0
    try:
        from server.models.cron import Cronjob

        cron_count = Cronjob.objects.filter(parent_project=project).count()
    except Exception:
        cron_count = 0
    return {
        "pk": project.pk,
        "name": getattr(project, "name", "") or f"Project {project.pk}",
        "description": getattr(project, "description", "") or "No description yet.",
        "path": getattr(project, "path", "") or "",
        "agent_count": agent_count,
        "session_count": session_count,
        "cron_count": cron_count,
    }


class ProjectsOverview(ModelView):
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="ws-ov-topbar">
            <div class="ws-ov-breadcrumb">
                <span class="ws-ov-crumb">Projects</span>
            </div>
            <div class="ws-ov-search">
                <svg class="ws-ov-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
                <input id="projectsOvSearch" placeholder="Search projects..." oninput="projectsOvFilter()" autocomplete="off">
            </div>
            <button class="ws-ov-primary" onclick="pyview.openCreate()">＋ New project</button>
        </div>
        <div class="main-view-body">
            <div class="main-view-content ws-ov-content">
                <div class="ws-ov-heading-row">
                    <div>
                        <h1 class="ws-ov-title">Projects</h1>
                        <div class="ws-ov-subtitle">{{ pyview.projects|length }} project(s), most recently active first</div>
                    </div>
                </div>
                <div class="ws-ov-grid" id="projectsOvGrid">
                    {% for project in pyview.projects %}
                    <div class="ws-ov-card" data-name="{{ project.name|lower }} {{ project.path|lower }}" onclick="pyview.openProject({{ project.pk }})">
                        <div class="ws-ov-card-top">
                            <div class="ws-ov-icon">
                                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                            </div>
                            <h3>{{ project.name }}</h3>
                        </div>
                        <div class="ws-ov-card-info">
                            <div class="ws-ov-path" title="{{ project.path }}">{{ project.path }}</div>
                            <div class="ws-ov-desc">{{ project.description }}</div>
                        </div>
                        <div class="ws-ov-card-bottom">
                            <div class="ws-ov-status">
                                {{ project.agent_count }} agent(s) · {{ project.session_count }} chat(s)
                            </div>
                            <span>{{ project.cron_count }} job(s)</span>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                <div class="ws-ov-empty" id="projectsOvEmpty" style="display:{% if pyview.projects %}none{% else %}block{% endif %}">
                    <div class="ws-ov-empty-icon">⌕</div>
                    <h2>No projects found</h2>
                    <div>Try another search or create a new project.</div>
                </div>
            </div>
        </div>
        <script>
            function projectsOvFilter() {
                var q = document.getElementById("projectsOvSearch").value.toLowerCase();
                var cards = document.querySelectorAll("#projectsOvGrid .ws-ov-card");
                var visible = 0;
                for (var i = 0; i < cards.length; i++) {
                    var match = cards[i].dataset.name.toLowerCase().indexOf(q) !== -1;
                    cards[i].style.display = match ? "" : "none";
                    if (match) visible++;
                }
                document.getElementById("projectsOvEmpty").style.display = visible ? "none" : "block";
            }
        </script>
    '''

    def __init__(self, subject: UiApp, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def projects(self) -> list[dict]:
        from server.models.project import Project

        try:
            all_projects = list(Project.objects.all().order_by("-updated_at"))
        except Exception:
            return []
        return [project_card_data(p) for p in all_projects]

    def openProject(self, pk: int) -> None:
        from server.models.project import Project
        from ui.main.project.project_view import ProjectView

        try:
            project = Project.objects.get(pk=int(pk))
        except (Project.DoesNotExist, ValueError, TypeError):
            return
        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(ProjectView, project)

    def openCreate(self) -> None:
        from ui.main.project.create import ProjectCreateView

        main_view = self._find_main_view()
        if main_view is not None:
            main_view.create_and_open_tab(ProjectCreateView, self.subject)

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent
