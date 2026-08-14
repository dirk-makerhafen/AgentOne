from __future__ import annotations
from typing import TYPE_CHECKING
from server.models.project import Project
from server.models.workspace import WorkspaceModel
from ui.lib.model_view import ModelView


if TYPE_CHECKING:
    from ui.main.rightpanel.project.rightpanel_project import RightPanelProject
    from ui.app import UiApp


class RightPanelProjectWorkspaces(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
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

    def __init__(self, subject: Project, parent: RightPanelProject, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def entries(self) -> list:
        p = self.subject
        if not p:
            return []
        return list(WorkspaceModel.objects.all().order_by("name"))

