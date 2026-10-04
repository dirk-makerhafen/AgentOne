from __future__ import annotations
from dataclasses import dataclass, field
from server.models.agents.agent import AgentModel
from ui.lib.model_view import ModelView
from typing import TYPE_CHECKING

from ui.main.rightpanel.agent.rightpanel_agent import RightPanelAgent

if TYPE_CHECKING:
    from ui.main.main_view import MainView


@dataclass
class CapabilityRow:
    name: str
    source_label: str
    allowed: bool


TYPE_CONFIG = [
    ("Tools",     "TOOL",     "toolRows"),
    ("Tasks",     "TASK",     "taskRows"),
    ("Commands",  "COMMAND",  "commandRows"),
    ("Skills",    "SKILL",    "skillRows"),
    ("Subagents", "SUBAGENT", "subagentRows"),
]


class AgentView(ModelView):
    RIGHTPANEL_VIEW = RightPanelAgent
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div style="display:None">
            def all_versions(self):
                pass
        </div>

        <div id="mainProfiles" class="main-view">
            <div class="main-view-header">
                <div class="main-view-title" id="profileDetailTitle">{{ pyview.agent.name }} </div>
                <div class="main-view-actions">
                <button id="btnActivateProfileDetail" class="panel-head-btn" title="Activate" data-i18n-title="profile_switch_title" onclick="activateCurrentProfile()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></button>
                <button id="btnDeleteProfileDetail" class="panel-head-btn" title="Delete" data-i18n-title="profile_delete_title" onclick="deleteCurrentProfile()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
                <button id="btnCancelProfileDetail" class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="cancelProfileForm()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
                <button id="btnSaveProfileDetail" class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="saveProfileForm()" style="display:none1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg></button>
                </div>
            </div>
            <div class="main-view-body" id="profileDetailBody">
                <div class="main-view-content">
                    <div class="detail-card">
                        <div class="detail-card-title">Agent</div>

                        <div class="detail-row">
                            <div class="detail-row-label">Name</div>
                            <div class="detail-row-value">{{ pyview.agent.name }}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Version</div>
                            <div class="detail-row-value">{{ pyview.agent.version_number }}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Extends</div>
                            <div class="detail-row-value">
                            {% for ea in pyview.extends_list %}
                                 {{ ea }}<br>
                            {% endfor %}
                            </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Status</div>
                            <div class="detail-row-value"><span class="detail-badge active">ACTIVE</span> <span class="detail-badge">(default)</span> </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Description</div>
                            <div class="detail-row-value">{{ pyview.agent.description }}</div>
                        </div>
                    </div>

                    <div class="detail-card">
                        <div class="detail-card-title">Settings</div>
                        <div style="display:flex; flex-direction: row; gap: 23px;">
                            <div style="width: stretch;">
                                <div class="detail-row">
                                    <div class="detail-row-label">Model</div>
                                    <div class="detail-row-value">{{pyview.agent.aimodel}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">Precision</div>
                                    <div class="detail-row-value">{{pyview.agent.precision}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">scheduler_strategy</div>
                                    <div class="detail-row-value">{{pyview.agent.scheduler_strategy}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">tool_call_syntax</div>
                                    <div class="detail-row-value">{{pyview.agent.tool_call_syntax}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">priority</div>
                                    <div class="detail-row-value">{{pyview.agent.priority}}</div>
                                </div>
                            </div>
                            <div style="width:stretch;">
                                <div class="detail-row">
                                    <div class="detail-row-label">max_retries</div>
                                    <div class="detail-row-value">{{pyview.agent.max_retries}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">max_turns</div>
                                    <div class="detail-row-value">{{pyview.agent.max_turns}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">max_unattended_turns</div>
                                    <div class="detail-row-value">{{pyview.agent.max_unattended_turns}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">max_history_messages</div>
                                    <div class="detail-row-value">{{pyview.agent.max_history_messages}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">auto_compact_max_tokens</div>
                                    <div class="detail-row-value">{{pyview.agent.auto_compact_max_tokens}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">auto_compact_min_tokens</div>
                                    <div class="detail-row-value">{{pyview.agent.auto_compact_min_tokens}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">auto_compact_idle_seconds</div>
                                    <div class="detail-row-value">{{pyview.agent.auto_compact_idle_seconds}}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">auto_compact_keep_percent</div>
                                    <div class="detail-row-value">{{pyview.agent.auto_compact_keep_percent}}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="detail-card">
                        <div class="detail-card-title">Tools</div>
                        {% if pyview.toolRows %}
                        <table class="capability-table" style="width:100%;border-collapse:collapse;font-size:12px">
                            <thead>
                                <tr style="border-bottom:1px solid var(--border2)">
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Name</th>
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Source</th>
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                            {% for row in pyview.toolRows %}
                                <tr style="border-bottom:1px solid var(--border2)">
                                    <td style="padding:4px 8px{% if not row.allowed %};text-decoration:line-through;color:var(--muted){% endif %}">{{ row.name }}</td>
                                    <td style="padding:4px 8px">{{ row.source_label }}</td>
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

                    <div class="detail-card">
                        <div class="detail-card-title">Tasks</div>
                        {% if pyview.taskRows %}
                        <table class="capability-table" style="width:100%;border-collapse:collapse;font-size:12px">
                            <thead>
                                <tr style="border-bottom:1px solid var(--border2)">
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Name</th>
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Source</th>
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                            {% for row in pyview.taskRows %}
                                <tr style="border-bottom:1px solid var(--border2)">
                                    <td style="padding:4px 8px{% if not row.allowed %};text-decoration:line-through;color:var(--muted){% endif %}">{{ row.name }}</td>
                                    <td style="padding:4px 8px">{{ row.source_label }}</td>
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

                    <div class="detail-card">
                        <div class="detail-card-title">Commands</div>
                        {% if pyview.commandRows %}
                        <table class="capability-table" style="width:100%;border-collapse:collapse;font-size:12px">
                            <thead>
                                <tr style="border-bottom:1px solid var(--border2)">
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Name</th>
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Source</th>
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                            {% for row in pyview.commandRows %}
                                <tr style="border-bottom:1px solid var(--border2)">
                                    <td style="padding:4px 8px{% if not row.allowed %};text-decoration:line-through;color:var(--muted){% endif %}">{{ row.name }}</td>
                                    <td style="padding:4px 8px">{{ row.source_label }}</td>
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

                    <div class="detail-card">
                        <div class="detail-card-title">Skills</div>
                        {% if pyview.skillRows %}
                        <table class="capability-table" style="width:100%;border-collapse:collapse;font-size:12px">
                            <thead>
                                <tr style="border-bottom:1px solid var(--border2)">
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Name</th>
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Source</th>
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                            {% for row in pyview.skillRows %}
                                <tr style="border-bottom:1px solid var(--border2)">
                                    <td style="padding:4px 8px{% if not row.allowed %};text-decoration:line-through;color:var(--muted){% endif %}">{{ row.name }}</td>
                                    <td style="padding:4px 8px">{{ row.source_label }}</td>
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

                    <div class="detail-card">
                        <div class="detail-card-title">Subagents</div>
                        {% if pyview.subagentRows %}
                        <table class="capability-table" style="width:100%;border-collapse:collapse;font-size:12px">
                            <thead>
                                <tr style="border-bottom:1px solid var(--border2)">
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Name</th>
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Source</th>
                                    <th style="text-align:left;padding:4px 8px;font-weight:600;color:var(--muted)">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                            {% for row in pyview.subagentRows %}
                                <tr style="border-bottom:1px solid var(--border2)">
                                    <td style="padding:4px 8px{% if not row.allowed %};text-decoration:line-through;color:var(--muted){% endif %}">{{ row.name }}</td>
                                    <td style="padding:4px 8px">{{ row.source_label }}</td>
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

                    <div class="detail-card">
                        <div class="detail-card-title">System Prompt</div>
                        <div class="detail-row">
                            <div style="min-height:0px; white-space: pre-line;height: 238px; overflow: auto; resize: auto;">
                                {{pyview.agent.system_prompt}}
                            </div>
                        </div>
                    </div>
                    
                </div>
            </div>
            <div class="main-view-empty" id="profileDetailEmpty" style="display:None">
                <svg class="main-view-empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <div class="main-view-empty-title" data-i18n="profiles_empty_title">Select a profile</div>
                <div class="main-view-empty-sub" data-i18n="profiles_empty_sub">Pick an agent profile from the sidebar to view and edit its settings, or create a new one.</div>
            </div>
        </div>
    '''

    def __init__(self, subject: AgentModel, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.agent = subject.get_runtime()
        self._toolRows: list[CapabilityRow] = []
        self._taskRows: list[CapabilityRow] = []
        self._commandRows: list[CapabilityRow] = []
        self._skillRows: list[CapabilityRow] = []
        self._subagentRows: list[CapabilityRow] = []
        self._build()

    @property
    def toolRows(self): return self._toolRows
    @property
    def taskRows(self): return self._taskRows
    @property
    def commandRows(self): return self._commandRows
    @property
    def skillRows(self): return self._skillRows
    @property
    def subagentRows(self): return self._subagentRows

    @property
    def extends_list(self):
        vm = self.agent.get_version_model()
        return [f"{ea.agent.name} v{ea.version_number}" for ea in vm.extends_agent_versions.all()]

    def _build(self):
        defined_tools_pks = set(self.agent.defined_tools.values_list("pk", flat=True))
        defined_tasks_pks = set(self.agent.defined_tasks.values_list("pk", flat=True))
        defined_commands_pks = set(self.agent.defined_commands.values_list("pk", flat=True))
        defined_skill_pks = set(self.agent.defined_skills.values_list("pk", flat=True))
        defined_subagent_pks = set(self.agent.defined_subagents.values_list("pk", flat=True))

        allowed_tools = set(self.agent.allowedToolNames)
        disallowed_tools = set(self.agent.disallowedToolNames)
        allowed_tasks = set(self.agent.allowedTaskNames)
        disallowed_tasks = set(self.agent.disallowedTaskNames)
        allowed_commands = set(self.agent.allowedCommandNames)
        disallowed_commands = set(self.agent.disallowedCommandNames)
        allowed_skills = set(self.agent.allowedSkillNames)
        disallowed_skills = set(self.agent.disallowedSkillNames)
        allowed_subagents = set(self.agent.allowedSubagentNames)
        disallowed_subagents = set(self.agent.disallowedSubagentNames)

        seen_tdv = set()
        seen_skill = set()
        seen_subagent = set()

        def add_tool(tdv):
            if tdv.pk in seen_tdv:
                return
            seen_tdv.add(tdv.pk)
            self._toolRows.append(CapabilityRow(
                tdv.task_definition.name,
                self._source_label(tdv, defined_tools_pks),
                self._check_allowed(tdv.task_definition.name, allowed_tools, disallowed_tools),
            ))

        def add_task(tdv):
            if tdv.pk in seen_tdv:
                return
            seen_tdv.add(tdv.pk)
            self._taskRows.append(CapabilityRow(
                tdv.task_definition.name,
                self._source_label(tdv, defined_tasks_pks),
                self._check_allowed(tdv.task_definition.name, allowed_tasks, disallowed_tasks),
            ))

        def add_command(tdv):
            if tdv.pk in seen_tdv:
                return
            seen_tdv.add(tdv.pk)
            self._commandRows.append(CapabilityRow(
                tdv.task_definition.name,
                self._source_label(tdv, defined_commands_pks),
                self._check_allowed(tdv.task_definition.name, allowed_commands, disallowed_commands),
            ))

        def add_skill(sv):
            if sv.pk in seen_skill:
                return
            seen_skill.add(sv.pk)
            self._skillRows.append(CapabilityRow(
                sv.skill.name,
                self._source_label(sv, defined_skill_pks),
                self._check_allowed(sv.skill.name, allowed_skills, disallowed_skills),
            ))

        def add_subagent(sav):
            if sav.pk in seen_subagent:
                return
            seen_subagent.add(sav.pk)
            self._subagentRows.append(CapabilityRow(
                sav.agent.name,
                self._source_label(sav, defined_subagent_pks),
                self._check_allowed(sav.agent.name, allowed_subagents, disallowed_subagents),
            ))

        for tdv in self.agent.all_tools:
            add_tool(tdv)
        for tdv in self.agent.defined_tools.select_related("task_definition").all():
            add_tool(tdv)

        for tdv in self.agent.all_tasks:
            add_task(tdv)
        for tdv in self.agent.defined_tasks.select_related("task_definition").all():
            add_task(tdv)

        for tdv in self.agent.all_commands:
            add_command(tdv)
        for tdv in self.agent.defined_commands.select_related("task_definition").all():
            add_command(tdv)

        for sv in self.agent.all_skills:
            add_skill(sv)
        for sv in self.agent.defined_skills.select_related("skill").all():
            add_skill(sv)
        if not seen_skill and self.agent.skillNames:
            from server.models.skills.skill_version import SkillModelVersion
            for sv in SkillModelVersion.objects.filter(
                skill__name__in=self.agent.skillNames
            ).select_related("skill").all():
                add_skill(sv)

        for sav in self.agent.all_subagents:
            add_subagent(sav)
        for sav in self.agent.defined_subagents.select_related("agent").all():
            add_subagent(sav)

        self._toolRows.sort(key=lambda r: r.name)
        self._taskRows.sort(key=lambda r: r.name)
        self._commandRows.sort(key=lambda r: r.name)
        self._skillRows.sort(key=lambda r: r.name)
        self._subagentRows.sort(key=lambda r: r.name)


    def _source_label(self, item, defined_pks) -> str:
        if item.pk in defined_pks:
            return "self"
        tdv = getattr(item, "task_definition", None)
        if tdv is not None:
            if tdv.parent_agent is None and tdv.parent_skill is None and tdv.parent_project is None:
                return "global"
            return "inherited"
        sv = getattr(item, "skill", None)
        if sv is not None:
            if sv.parent_agent is None and sv.parent_skill is None and sv.parent_project is None:
                return "global"
            return "inherited"
        av = getattr(item, "agent", None)
        if av is not None:
            if av.parent_agent is None and av.parent_skill is None and av.parent_project is None:
                return "global"
            return "inherited"
        return "inherited"


    def _check_allowed(self, name: str, allowed_set: set, disallowed_set: set) -> bool:
        if name in disallowed_set:
            return False
        return name in allowed_set
