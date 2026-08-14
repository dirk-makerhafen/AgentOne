from __future__ import annotations
from typing import TYPE_CHECKING
from django.utils import timezone
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.rightpanel.agent.rightpanel_agent import RightPanelAgent
    from ui.app import UiApp


class RightPanelAgentInfo(PyHtmlView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Info</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            <div class="settings-card" style="margin-bottom:8px">
                <div class="detail-row">
                    <div class="detail-row-label">Model</div>
                    <div class="detail-row-value">{{ pyview.subject.model }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Version</div>
                    <div class="detail-row-value">{{ pyview.version_number }}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Extends</div>
                    <div class="detail-row-value">{% if pyview.extends_names %}{{ pyview.extends_names|join(", ") }}{% else %}&mdash;{% endif %}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Status</div>
                    <div class="detail-row-value">
                        {% if pyview.subject.is_active %}
                            <span style="color:var(--success)">active</span>
                        {% else %}
                            <span style="color:var(--error)">inactive</span>
                        {% endif %}
                    </div>
                </div>
                <div class="detail-row">
                    <div class="detail-row-label">Sessions</div>
                    <div class="detail-row-value">{{ pyview.session_count }}</div>
                </div>
            </div>
            <div class="settings-card">
                <div class="panel-header" style="margin-left:-8px">Description</div>
                <div style="font-size:12px;color:var(--text);white-space:pre-line;max-height:200px;overflow:auto;margin-top:4px">{{ pyview.subject.description }}</div>
            </div>
        </div>
    '''

    def __init__(self, subject: AgentModel, parent: RightPanelAgent, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def extends_names(self) -> list[str]:
        a = self.subject
        if a and a.latest_agent_version:
            return a.latest_agent_version.extends_agent_names or []
        return []

    @property
    def version_number(self) -> str:
        a = self.subject
        if a and a.latest_agent_version:
            return str(a.latest_agent_version.version_number)
        return "\u2014"

    @property
    def session_count(self) -> int:
        a = self.subject
        if a:
            return SessionModel.objects.filter(latest_session_version__agent=a).count()
        return 0

