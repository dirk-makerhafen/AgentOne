from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from server.models.cron import Cronjob
from server.models.sessions.session import SessionModel
from server.models.workspace import WorkspaceModel
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.rightpanel.workspace.rightpanel_workspace import RightPanelWorkspace


class RightPanelWorkspaceUsage(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Usage</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            <div class="panel-header" style="margin-left:-8px">Related cron jobs</div>
            {% if pyview.cron_jobs %}
                {% for c in pyview.cron_jobs %}
                <div style="display:flex;align-items:center;padding:6px 2px;font-size:12px;border-bottom:1px solid var(--border,.05)">
                    <span style="font-weight:500">{{ c.name }}</span>
                </div>
                {% endfor %}
            {% else %}
                <div style="font-size:12px;color:var(--muted);padding:4px 2px 12px">None</div>
            {% endif %}
            <div class="panel-header" style="margin-left:-8px">Related sessions</div>
            {% if pyview.sessions %}
                {% for s in pyview.sessions %}
                <div style="display:flex;align-items:center;padding:6px 2px;font-size:12px;border-bottom:1px solid var(--border,.05)">
                    <span style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ s.name }}</span>
                </div>
                {% endfor %}
            {% else %}
                <div style="font-size:12px;color:var(--muted);padding:4px 2px">None</div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: WorkspaceModel, parent: RightPanelWorkspace, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def cron_jobs(self) -> list:
        ws = self.subject
        if not ws:
            return []
        return list(Cronjob.objects.filter(workspace=ws).order_by("name"))

    @property
    def sessions(self) -> list:
        ws = self.subject
        if not ws:
            return []
        return list(SessionModel.objects.filter(latest_session_version__workspace=ws).order_by("-created_at")[:20])

