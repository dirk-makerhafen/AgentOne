from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.project import Project
from server.models.workspace import WorkspaceModel
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from server.models.cron import Cronjob
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.rightpanel.project.rightpanel_project import RightPanelProject


class RightPanelProjectOverview(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
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

    def __init__(self, subject: Project, parent: RightPanelProject, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def agent_count(self) -> int:
        p = self.subject
        return AgentModel.objects.filter(parent_project=p).count() if p else 0

    @property
    def session_count(self) -> int:
        p = self.subject
        if not p:
            return 0
        return SessionModel.objects.filter(parent_project=p).count()

    @property
    def cron_count(self) -> int:
        p = self.subject
        return Cronjob.objects.filter(parent_project=p).count() if p else 0

    @property
    def workspace_count(self) -> int:
        p = self.subject
        if not p:
            return 0
        return WorkspaceModel.objects.filter().count()
