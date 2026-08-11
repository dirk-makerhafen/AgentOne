from __future__ import annotations
from typing import TYPE_CHECKING
from django.utils import timezone
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


AGENT_ICONS = {
    "info": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    "sessions": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    "capabilities": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
}


class RightPanelAgentInfo(PyHtmlView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Info</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            <div class="settings-card" style="margin-bottom:8px">
                <div class="detail-row">
                    <div class="detail-row-label">Model</div>
                    <div class="detail-row-value">{{ pyview.agent.model }}</div>
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
                        {% if pyview.agent.is_active %}
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
                <div style="font-size:12px;color:var(--text);white-space:pre-line;max-height:200px;overflow:auto;margin-top:4px">{{ pyview.agent.description }}</div>
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def agent(self) -> AgentModel | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, AgentModel) else None

    @property
    def extends_names(self) -> list[str]:
        a = self.agent
        if a and a.latest_agent_version:
            return a.latest_agent_version.extends_agent_names or []
        return []

    @property
    def version_number(self) -> str:
        a = self.agent
        if a and a.latest_agent_version:
            return str(a.latest_agent_version.version_number)
        return "\u2014"

    @property
    def session_count(self) -> int:
        a = self.agent
        if a:
            return SessionModel.objects.filter(latest_session_version__agent=a).count()
        return 0


class RightPanelAgentSessions(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
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

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def agent(self) -> AgentModel | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, AgentModel) else None

    @property
    def entries(self) -> list[dict]:
        a = self.agent
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


class RightPanelAgentCapabilities(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Capabilities</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% for section in pyview.sections %}
            <div style="margin-bottom:8px">
                <div class="panel-header" style="margin-left:-8px">{{ section.title }}</div>
                {% if section.rows %}
                    <table style="width:100%;border-collapse:collapse;font-size:12px">
                        <thead>
                            <tr style="border-bottom:1px solid var(--border2)">
                                <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Name</th>
                                <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                        {% for row in section.rows %}
                            <tr style="border-bottom:1px solid var(--border2)">
                                <td style="padding:4px 8px{% if not row.allowed %};text-decoration:line-through;color:var(--muted){% endif %}">{{ row.name }}</td>
                                <td style="padding:4px 8px">
                                {% if row.allowed %}
                                    <span style="color:var(--success)">allowed</span>
                                {% else %}
                                    <span style="color:var(--danger)">disallowed</span>
                                {% endif %}
                                </td>
                            </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                {% else %}
                    <div style="font-size:12px;color:var(--muted);padding:8px">None</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def agent(self) -> AgentModel | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, AgentModel) else None

    @property
    def sections(self) -> list:
        a = self.agent
        if not a:
            return []
        from dataclasses import dataclass
        from server.models.agents.agent_version import AgentVersionModel

        @dataclass
        class CapRow:
            name: str
            allowed: bool

        @dataclass
        class Section:
            title: str
            rows: list

        av = a.latest_agent_version
        if not av:
            return []

        def _build(allowed, disallowed):
            seen = set()
            rows = []
            for name in sorted(allowed | disallowed):
                if name in seen:
                    continue
                seen.add(name)
                rows.append(CapRow(name, name not in disallowed))
            return rows

        sections = []
        pairs = [
            ("Tools",     "toolNames",     "disallowedToolNames"),
            ("Tasks",     "taskNames",     "disallowedTaskNames"),
            ("Commands",  "commandNames",  "disallowedCommandNames"),
            ("Skills",    "skillNames",    "disallowedSkillNames"),
            ("Subagents", "subagentNames", "disallowedSubagentNames"),
        ]
        for title, allowed_attr, disallowed_attr in pairs:
            allowed = set(av.resolve_setting(allowed_attr) or [])
            disallowed = set(av.resolve_setting(disallowed_attr) or [])
            rows = _build(allowed, disallowed)
            sections.append(Section(title, rows))
        return sections
