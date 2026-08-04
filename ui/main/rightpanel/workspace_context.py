from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.workspace import WorkspaceModel
from server.models.cron import Cronjob
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


WORKSPACE_ICONS = {
    "files": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
    "usage": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
}


class RightPanelWorkspaceUsage(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
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

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def workspace(self) -> WorkspaceModel | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, WorkspaceModel) else None

    @property
    def cron_jobs(self) -> list:
        ws = self.workspace
        if not ws:
            return []
        return list(Cronjob.objects.filter(workspace=ws).order_by("name"))

    @property
    def sessions(self) -> list:
        ws = self.workspace
        if not ws:
            return []
        return list(SessionModel.objects.filter(latest_session_version__workspace=ws).order_by("-created_at")[:20])
