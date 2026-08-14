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


class RightPanelAgentSessions(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Sessions</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% if pyview.entries %}
                {% for entry in pyview.entries %}
                <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 2px;font-size:12px;border-bottom:1px solid var(--border,.05)">
                    <div style="min-width:0;flex:1">
                        <div style="font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ entry.name }}</div>
                    </div>
                    <span style="color:var(--muted);font-size:11px;flex-shrink:0">{{ entry.since }}</span>
                </div>
                {% endfor %}
            {% else %}
                <div style="font-size:12px;color:var(--muted);padding:8px">No sessions yet.</div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: AgentModel, parent: RightPanelAgent, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def entries(self) -> list[dict]:
        a = self.subject
        if not a:
            return []
        from datetime import datetime, timezone as dt_timezone
        now = timezone.now()
        qs = SessionModel.objects.filter(
            latest_session_version__agent=a,
        ).order_by("-created_at")[:20]
        rows = []
        for s in qs:
            dt = s.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=dt_timezone.utc)
            diff = now - dt
            secs = int(diff.total_seconds())
            if secs < 5:
                since = "just now"
            elif secs < 60:
                since = f"{secs}s ago"
            elif secs < 3600:
                since = f"{secs // 60}m ago"
            elif secs < 86400:
                since = f"{secs // 3600}h ago"
            else:
                since = f"{secs // 86400}d ago"
            rows.append({"name": s.name or s.latest_session_version.agent.name if s.latest_session_version else "?", "since": since, "pk": s.pk})
        return rows
