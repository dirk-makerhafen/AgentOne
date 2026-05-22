from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass
from runtime.session.session import Session
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


@dataclass
class CapabilityRow:
    name: str
    allowed: bool


@dataclass
class Section:
    title: str
    rows: list[CapabilityRow]


def _build_category(allowed_names: set[str], disallowed_names: set[str]) -> list[CapabilityRow]:
    seen = set()
    rows = []
    for name in sorted(allowed_names | disallowed_names):
        if name in seen:
            continue
        seen.add(name)
        rows.append(CapabilityRow(name, name not in disallowed_names))
    print("ROWS", rows)
    return rows


class RightPanelTasks(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        <div class="panel-header">
            <span>Capabilities</span>
        </div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% for section in pyview.sections %}
            <div class="task-card" style="margin-bottom:8px">
             <div class="panel-header" style="margin-left:-8px">{{ section.title }}</div>
                {% if section.rows %}
                    <table class="capability-table" style="width:100%;border-collapse:collapse;font-size:12px">
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
                    <div class="detail-row">
                        <div class="detail-row-value" style="color:var(--muted);font-size:12px">None</div>
                    </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._toolRows: list[CapabilityRow] = []
        self._taskRows: list[CapabilityRow] = []
        self._commandRows: list[CapabilityRow] = []
        self._skillRows: list[CapabilityRow] = []
        self._subagentRows: list[CapabilityRow] = []
        #self._build()
        print("FIIBAR")

    @property
    def sections(self):
        self._build()
        self.s = [
            Section("Tools", self._toolRows),
            Section("Tasks", self._taskRows),
            Section("Commands", self._commandRows),
            Section("Skills", self._skillRows),
            Section("Subagents", self._subagentRows),
        ]
        print(self.s)
        return self.s

    @property
    def session(self) -> Session | None:
        return self.parent.current_session

    def _build(self):
        s = self.session
        if s is None:
            self._toolRows.clear()
            self._taskRows.clear()
            self._commandRows.clear()
            self._skillRows.clear()
            self._subagentRows.clear()
            return
        self._toolRows[:] = _build_category(set(s.allowedToolNames), set(s.disallowedToolNames))
        self._taskRows[:] = _build_category(set(s.allowedTaskNames), set(s.disallowedTaskNames))
        self._commandRows[:] = _build_category(set(s.allowedCommandNames), set(s.disallowedCommandNames))
        self._skillRows[:] = _build_category(set(s.allowedSkillNames), set(s.disallowedSkillNames))
        self._subagentRows[:] = _build_category(set(s.allowedSubagentNames), set(s.disallowedSubagentNames))
        print("FIIBAR1", self._taskRows)

    def update(self, *args, **kwargs):
        self._build()
        super().update(*args, **kwargs)
