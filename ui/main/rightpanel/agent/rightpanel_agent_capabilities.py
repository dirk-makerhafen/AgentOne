from __future__ import annotations
from typing import TYPE_CHECKING
from django.utils import timezone
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView


if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.rightpanel.agent.rightpanel_agent import RightPanelAgent

class RightPanelAgentCapabilities(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
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

    def __init__(self, subject: AgentModel, parent: RightPanelAgent, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def sections(self) -> list:
        a = self.subject
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

