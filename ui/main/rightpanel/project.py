from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.project import Project
from server.models.workspace import WorkspaceModel
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from server.models.cron import Cronjob
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


PROJECT_ICONS = {
    "overview": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
    "workspaces": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
}


class RightPanelProjectOverview(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Overview</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            <div class="settings-card" style="margin-bottom:8px">
                <div class="detail-row">
                    <div class="detail-row-label">Path</div>
                    <div class="detail-row-value"><code style="font-size:11px">{{ pyview.project.path }}</code></div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Description</div>
                    <div class="detail-row-value" style="white-space:pre-line;max-height:80px;overflow:auto;font-size:12px">{{ pyview.project.description }}</div>
                </div>
            </div>
            <div class="settings-card">
                <div class="panel-header" style="margin-left:-8px">Stats</div>
                <div class="detail-row">
                    <div class="detail-row-label">Agents</div>
                    <div class="detail-row-value">{{ pyview.agent_count }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Sessions</div>
                    <div class="detail-row-value">{{ pyview.session_count }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Cron jobs</div>
                    <div class="detail-row-value">{{ pyview.cron_count }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Workspaces</div>
                    <div class="detail-row-value">{{ pyview.workspace_count }}</div>
                </div>
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def project(self) -> Project | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, Project) else None

    @property
    def agent_count(self) -> int:
        p = self.project
        return AgentModel.objects.filter(parent_project=p).count() if p else 0

    @property
    def session_count(self) -> int:
        p = self.project
        if not p:
            return 0
        return SessionModel.objects.filter(parent_project=p).count()

    @property
    def cron_count(self) -> int:
        p = self.project
        return Cronjob.objects.filter(parent_project=p).count() if p else 0

    @property
    def workspace_count(self) -> int:
        p = self.project
        if not p:
            return 0
        return WorkspaceModel.objects.filter().count()


class RightPanelProjectWorkspaces(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Workspaces</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% if pyview.entries %}
                {% for ws in pyview.entries %}
                <div style="display:flex;align-items:center;gap:6px;padding:6px 2px;font-size:12px;border-bottom:1px solid var(--border,.05)">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                    <div style="min-width:0;flex:1">
                        <div style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ ws.name }}</div>
                        <div style="font-size:10px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ ws.path }}</div>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div style="font-size:12px;color:var(--muted);padding:8px">No workspaces.</div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def project(self) -> Project | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, Project) else None

    @property
    def entries(self) -> list:
        p = self.project
        if not p:
            return []
        return list(WorkspaceModel.objects.all().order_by("name"))
