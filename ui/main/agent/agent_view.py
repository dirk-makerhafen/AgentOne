from __future__ import annotations
from dataclasses import dataclass, field
from django.db.models import Count, Avg, Sum, Q
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
    call_count: int = 0
    failure_count: int = 0


TYPE_CONFIG = [
    ("Tools",     "TOOL",     "toolRows"),
    ("Tasks",     "TASK",     "taskRows"),
    ("Commands",  "COMMAND",  "commandRows"),
    ("Skills",    "SKILL",    "skillRows"),
    ("Subagents", "SUBAGENT", "subagentRows"),
]


def format_tokens(n: int) -> str:
    """Format token count with K/M suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_time(seconds: float) -> str:
    """Format duration in seconds to human-readable."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


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
                <div class="main-view-title" id="profileDetailTitle">{{ pyview.agent.name }}</div>
                <div class="main-view-actions">
                    {% if not pyview.editing %}
                    <button id="btnEditProfileDetail" class="panel-head-btn" title="Edit agent" data-i18n-title="edit" onclick="editCurrentProfile()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                    </button>
                    <button id="btnDeleteProfileDetail" class="panel-head-btn" title="Delete agent" data-i18n-title="delete" onclick="deleteCurrentProfile()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                    {% else %}
                    <button id="btnCancelProfileDetail" class="panel-head-btn" title="Cancel" data-i18n-title="cancel" onclick="cancelProfileForm()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                    </button>
                    <button id="btnSaveProfileDetail" class="panel-head-btn primary" title="Save" data-i18n-title="save" onclick="saveProfileForm()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                    </button>
                    {% endif %}
                </div>
            </div>
            <div class="main-view-body" id="profileDetailBody">
                <div class="main-view-content">
                    {% if pyview.editing %}
                    <!-- EDIT MODE -->
                    <div class="detail-card">
                        <div class="detail-card-title">Edit Agent</div>
                        <form class="detail-form" onsubmit="event.preventDefault(); saveProfileForm();">
                            <div class="detail-form-row">
                                <label for="agentName">Name</label>
                                <input type="text" id="agentName" value="{{ pyview._edit_data.name }}" onchange="pyview.setField('name', this.value)" placeholder="Agent name">
                            </div>
                            <div class="detail-form-row">
                                <label for="agentModel">Model</label>
                                <input type="text" id="agentModel" value="{{ pyview._edit_data.aimodel }}" onchange="pyview.setField('aimodel', this.value)" placeholder="Model name">
                            </div>
                            <div class="detail-form-row">
                                <label for="agentDescription">Description / System Prompt</label>
                                <textarea id="agentDescription" rows="6" onchange="pyview.setField('description', this.value)" placeholder="Agent description and system prompt">{{ pyview._edit_data.description }}</textarea>
                            </div>
                            <div class="detail-form-row">
                                <label for="agentPriority">Priority</label>
                                <input type="number" id="agentPriority" value="{{ pyview._edit_data.priority }}" min="0" max="99" onchange="pyview.setField('priority', this.value)">
                            </div>
                            <div class="detail-form-row">
                                <label for="agentMaxTurns">Max Turns</label>
                                <input type="number" id="agentMaxTurns" value="{{ pyview._edit_data.max_turns }}" min="0" onchange="pyview.setField('max_turns', this.value)">
                            </div>
                            <div class="detail-form-row">
                                <label for="agentMaxUnattended">Max Unattended Turns</label>
                                <input type="number" id="agentMaxUnattended" value="{{ pyview._edit_data.max_unattended_turns }}" min="0" onchange="pyview.setField('max_unattended_turns', this.value)">
                            </div>
                            <div class="detail-form-row">
                                <label for="agentMaxRetries">Max Retries</label>
                                <input type="number" id="agentMaxRetries" value="{{ pyview._edit_data.max_retries }}" min="0" onchange="pyview.setField('max_retries', this.value)">
                            </div>
                            {% if pyview._edit_error %}
                            <div class="detail-form-error">{{ pyview._edit_error }}</div>
                            {% endif %}
                        </form>
                    </div>
                    {% else %}
                    <!-- VIEW MODE -->
                    <!-- STATISTICS SECTION -->
                    <div class="detail-card">
                        <div class="detail-card-title">Statistics</div>
                        <div class="stats-grid">
                            <div class="stat-item">
                                <div class="stat-icon">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                                </div>
                                <div class="stat-value">{{ pyview.stats.session_count }}</div>
                                <div class="stat-label">Sessions</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-icon">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>
                                </div>
                                <div class="stat-value">{{ pyview.stats.run_count }}</div>
                                <div class="stat-label">Task Runs</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-icon">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                                </div>
                                <div class="stat-value">{{ pyview.stats.message_count }}</div>
                                <div class="stat-label">Messages</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-icon">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                                </div>
                                <div class="stat-value">{{ pyview.stats.tokens_display }}</div>
                                <div class="stat-label">Tokens</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-icon">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                                </div>
                                <div class="stat-value">{{ pyview.stats.avg_run_time_display }}</div>
                                <div class="stat-label">Avg Run Time</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-icon">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                                </div>
                                <div class="stat-value{% if pyview.stats.failure_rate > 5 %} stat-value--error{% endif %}">{{ pyview.stats.failure_rate }}%</div>
                                <div class="stat-label">Failure Rate</div>
                            </div>
                        </div>
                        {% if pyview.stats.success_run_count > 0 or pyview.stats.failure_run_count > 0 %}
                        <div class="stats-bar">
                            <div class="stats-bar-segment stats-bar--success" style="width:{{ pyview.stats.success_pct }}%">
                                <span class="stats-bar-label">{{ pyview.stats.success_run_count }}</span>
                            </div>
                            {% if pyview.stats.failure_run_count > 0 %}
                            <div class="stats-bar-segment stats-bar--failure" style="width:{{ pyview.stats.failure_pct }}%">
                                <span class="stats-bar-label">{{ pyview.stats.failure_run_count }}</span>
                            </div>
                            {% endif %}
                        </div>
                        {% endif %}
                    </div>

                    <!-- AGENT INFO -->
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
                            {% if not pyview.extends_list %}
                                —
                            {% endif %}
                            </div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Status</div>
                            <div class="detail-row-value"><span class="detail-badge active">ACTIVE</span> <span class="detail-badge">(default)</span></div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-row-label">Description</div>
                            <div class="detail-row-value">{{ pyview.agent.description }}</div>
                        </div>
                    </div>

                    <!-- SETTINGS -->
                    <div class="detail-card">
                        <div class="detail-card-title">Settings</div>
                        <div class="settings-grid">
                            <div class="settings-column">
                                <div class="detail-row">
                                    <div class="detail-row-label">Model</div>
                                    <div class="detail-row-value">{{ pyview.agent.aimodel }}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">Reasoning</div>
                                    <div class="detail-row-value">{{ pyview.agent.reasoning_effort }}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">Scheduler</div>
                                    <div class="detail-row-value">{{ pyview.agent.scheduler_strategy }}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">Tool Call Syntax</div>
                                    <div class="detail-row-value">{{ pyview.agent.tool_call_syntax }}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">Priority</div>
                                    <div class="detail-row-value">{{ pyview.agent.priority }}</div>
                                </div>
                            </div>
                            <div class="settings-column">
                                <div class="detail-row">
                                    <div class="detail-row-label">Max Retries</div>
                                    <div class="detail-row-value">{{ pyview.agent.max_retries }}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">Max Turns</div>
                                    <div class="detail-row-value">{{ pyview.agent.max_turns }}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">Max Unattended</div>
                                    <div class="detail-row-value">{{ pyview.agent.max_unattended_turns }}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">Max History</div>
                                    <div class="detail-row-value">{{ pyview.agent.max_history_messages }}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">Compact Max Tokens</div>
                                    <div class="detail-row-value">{{ pyview.agent.auto_compact_max_tokens }}</div>
                                </div>
                            </div>
                            <div class="settings-column">
                                <div class="detail-row">
                                    <div class="detail-row-label">Compact Min Tokens</div>
                                    <div class="detail-row-value">{{ pyview.agent.auto_compact_min_tokens }}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">Compact Idle Seconds</div>
                                    <div class="detail-row-value">{{ pyview.agent.auto_compact_idle_seconds }}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-row-label">Compact Keep %</div>
                                    <div class="detail-row-value">{{ pyview.agent.auto_compact_keep_percent }}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- CAPABILITIES -->
                    {% for section_name, section_type, section_var in pyview.type_config %}
                    <div class="detail-card">
                        <div class="detail-card-title">{{ section_name }}</div>
                        {% if pyview[section_var] %}
                        <table class="capability-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Calls</th>
                                    <th>Source</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                            {% for row in pyview[section_var] %}
                                <tr>
                                    <td{% if not row.allowed %} class="capability-disabled"{% endif %}>{{ row.name }}</td>
                                    <td>
                                        {% if row.call_count > 0 %}
                                        <span class="capability-calls">
                                            {{ row.call_count }}
                                            {% if row.failure_count > 0 %}
                                            <span class="capability-calls--fail">{{ row.failure_count }}✗</span>
                                            {% endif %}
                                        </span>
                                        {% else %}
                                        <span class="capability-calls--none">—</span>
                                        {% endif %}
                                    </td>
                                    <td>{{ row.source_label }}</td>
                                    <td>
                                    {% if row.allowed %}
                                        <span class="capability-status capability-status--allowed">allowed</span>
                                    {% else %}
                                        <span class="capability-status capability-status--disallowed">disallowed</span>
                                    {% endif %}
                                    </td>
                                </tr>
                            {% endfor %}
                            </tbody>
                        </table>
                        {% else %}
                        <div class="detail-row">
                            <div class="detail-row-value detail-row-value--empty">None</div>
                        </div>
                        {% endif %}
                    </div>
                    {% endfor %}

                    <!-- SYSTEM PROMPT -->
                    <div class="detail-card">
                        <div class="detail-card-title">System Prompt</div>
                        <div class="detail-row">
                            <div class="system-prompt-box">{{ pyview.agent.system_prompt }}</div>
                        </div>
                    </div>
                    {% endif %}
                </div>
            </div>
            <div class="main-view-empty" id="profileDetailEmpty" style="display:None">
                <svg class="main-view-empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <div class="main-view-empty-title" data-i18n="profiles_empty_title">Select a profile</div>
                <div class="main-view-empty-sub" data-i18n="profiles_empty_sub">Pick an agent profile from the sidebar to view and edit its settings, or create a new one.</div>
            </div>
        </div>
        <script>
            function editCurrentProfile() {
                ; pyview.startEdit();
            }

            function cancelProfileForm() {
                ; pyview.cancelEdit();
            }

            function saveProfileForm() {
                // Read current form values (they may have changed via onchange)
                var nameEl = document.getElementById("agentName");
                var modelEl = document.getElementById("agentModel");
                var descEl = document.getElementById("agentDescription");
                var priorityEl = document.getElementById("agentPriority");
                var maxTurnsEl = document.getElementById("agentMaxTurns");
                var maxUnattendedEl = document.getElementById("agentMaxUnattended");
                var maxRetriesEl = document.getElementById("agentMaxRetries");

                if (nameEl)  { ; pyview.setField('name', nameEl.value); }
                if (modelEl) { ; pyview.setField('aimodel', modelEl.value); }
                if (descEl)  { ; pyview.setField('description', descEl.value); }
                if (priorityEl) { ; pyview.setField('priority', priorityEl.value); }
                if (maxTurnsEl) { ; pyview.setField('max_turns', maxTurnsEl.value); }
                if (maxUnattendedEl) { ; pyview.setField('max_unattended_turns', maxUnattendedEl.value); }
                if (maxRetriesEl) { ; pyview.setField('max_retries', maxRetriesEl.value); }

                ; pyview.saveEdit();
            }

            function deleteCurrentProfile() {
                if (confirm('Delete agent "{{ pyview.agent.name }}"? This cannot be undone.')) {
                    ; pyview.deleteAgent({{ pyview.agent.pk }});
                }
            }
        </script>
    '''

    def __init__(self, subject: AgentModel, parent: MainView, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self.agent = subject.get_runtime()
        self._toolRows: list[CapabilityRow] = []
        self._taskRows: list[CapabilityRow] = []
        self._commandRows: list[CapabilityRow] = []
        self._skillRows: list[CapabilityRow] = []
        self._subagentRows: list[CapabilityRow] = []
        self._editing = False
        self._edit_data: dict = {}
        self._edit_error = ""
        self._stats: dict = {}
        self._build()

    @property
    def type_config(self):
        return TYPE_CONFIG

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

    @property
    def editing(self):
        return self._editing

    @property
    def edit_data(self):
        return self._edit_data

    @property
    def edit_error(self):
        return self._edit_error

    @property
    def stats(self):
        return self._stats

    def _build(self):
        # Build capability rows
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

        # Build task call stats lookup (per task name)
        from server.models.tasks.agent_task_call import AgentTaskCall
        from django.db.models import F, Case, When, IntegerField

        agent_model = self.agent.model
        task_call_stats = {}
        try:
            stats_qs = AgentTaskCall.objects.filter(
                session_version__session__latest_session_version__agent=agent_model
            ).annotate(
                task_name=F('task_definition__name'),
                is_failure=Case(
                    When(status_detail__in=['ENDED_FAILURE_EXCEPTION', 'ENDED_FAILURE_LOGIC'], then=1),
                    default=0,
                    output_field=IntegerField()
                )
            ).values('task_name').annotate(
                call_count=Count('pk'),
                failure_count=Sum('is_failure')
            )
            for stat in stats_qs:
                task_call_stats[stat['task_name']] = {
                    'call_count': stat['call_count'],
                    'failure_count': stat['failure_count'] or 0,
                }
        except Exception:
            pass

        def add_tool(tdv):
            if tdv.pk in seen_tdv:
                return
            seen_tdv.add(tdv.pk)
            stats = task_call_stats.get(tdv.task_definition.name, {'call_count': 0, 'failure_count': 0})
            self._toolRows.append(CapabilityRow(
                tdv.task_definition.name,
                self._source_label(tdv, defined_tools_pks),
                self._check_allowed(tdv.task_definition.name, allowed_tools, disallowed_tools),
                stats['call_count'],
                stats['failure_count'],
            ))

        def add_task(tdv):
            if tdv.pk in seen_tdv:
                return
            seen_tdv.add(tdv.pk)
            stats = task_call_stats.get(tdv.task_definition.name, {'call_count': 0, 'failure_count': 0})
            self._taskRows.append(CapabilityRow(
                tdv.task_definition.name,
                self._source_label(tdv, defined_tasks_pks),
                self._check_allowed(tdv.task_definition.name, allowed_tasks, disallowed_tasks),
                stats['call_count'],
                stats['failure_count'],
            ))

        def add_command(tdv):
            if tdv.pk in seen_tdv:
                return
            seen_tdv.add(tdv.pk)
            stats = task_call_stats.get(tdv.task_definition.name, {'call_count': 0, 'failure_count': 0})
            self._commandRows.append(CapabilityRow(
                tdv.task_definition.name,
                self._source_label(tdv, defined_commands_pks),
                self._check_allowed(tdv.task_definition.name, allowed_commands, disallowed_commands),
                stats['call_count'],
                stats['failure_count'],
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

        # Build statistics
        self._build_stats()

        # Initialize edit data if in editing mode
        if self._editing:
            self._edit_data = {
                "name": self.agent.name,
                "aimodel": self.agent.aimodel.name if self.agent.aimodel else "",
                "description": self.agent.description or "",
                "priority": self.agent.priority,
                "max_turns": self.agent.max_turns,
                "max_unattended_turns": self.agent.max_unattended_turns,
                "max_retries": self.agent.max_retries,
            }

    def _build_stats(self):
        """Build statistics for the agent."""
        try:
            from server.models.sessions.session import SessionModel
            from server.models.message import Message
            from server.models.queries.response import Response
            from server.models.tasks.agent_task_call import AgentTaskCall
            from server.models.tasks.agent_task_run import AgentTaskRun
            from server.models.enums.task_enums import TaskRunStatus
            from django.db.models.functions import Extract
            from django.db.models import F

            agent_model = self.agent.model

            # Sessions
            sessions = SessionModel.objects.filter(
                latest_session_version__agent=agent_model
            )
            session_count = sessions.count()

            # Messages
            messages = Message.objects.filter(
                session_version__session__latest_session_version__agent=agent_model
            )
            message_count = messages.count()

            # Tokens
            responses = Response.objects.filter(
                session_version__session__latest_session_version__agent=agent_model
            )
            total_prompt_tokens = responses.aggregate(total=Sum("prompt_tokens"))["total"] or 0
            total_completion_tokens = responses.aggregate(total=Sum("completion_tokens"))["total"] or 0
            total_tokens = int(total_prompt_tokens + total_completion_tokens)

            # Task runs
            runs = AgentTaskRun.objects.filter(
                session_version__session__latest_session_version__agent=agent_model
            )
            run_count = runs.count()
            success_run_count = runs.filter(status=TaskRunStatus.SUCCESS).count()
            failure_run_count = runs.filter(status=TaskRunStatus.FAILURE).count()

            # Average run duration
            avg_run_time = 0
            try:
                durations = runs.filter(
                    Q(created_at__isnull=False) & Q(ended_at__isnull=False)
                ).annotate(
                    duration_sec=Extract(F("ended_at") - F("created_at"), "epoch")
                ).aggregate(avg=Avg("duration_sec"))["avg"]
                if durations:
                    avg_run_time = float(durations)
            except Exception:
                pass

            # Failure rate
            failure_rate = 0
            if run_count > 0:
                failure_rate = round((failure_run_count / run_count) * 100, 1)

            # Success/failure percentages
            success_pct = 0
            failure_pct = 0
            if run_count > 0:
                success_pct = round((success_run_count / run_count) * 100)
                failure_pct = 100 - success_pct

            self._stats = {
                "session_count": session_count,
                "message_count": message_count,
                "tokens_display": format_tokens(total_tokens),
                "run_count": run_count,
                "success_run_count": success_run_count,
                "failure_run_count": failure_run_count,
                "avg_run_time": avg_run_time,
                "avg_run_time_display": format_time(avg_run_time),
                "failure_rate": failure_rate,
                "success_pct": success_pct,
                "failure_pct": failure_pct,
            }
        except Exception:
            self._stats = {
                "session_count": 0,
                "message_count": 0,
                "tokens_display": "0",
                "run_count": 0,
                "success_run_count": 0,
                "failure_run_count": 0,
                "avg_run_time": 0,
                "avg_run_time_display": "0s",
                "failure_rate": 0,
                "success_pct": 0,
                "failure_pct": 0,
            }

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

    # ------------------------------------------------------------------
    # Edit actions
    # ------------------------------------------------------------------

    def startEdit(self) -> None:
        """Enter edit mode."""
        self._editing = True
        self._edit_error = ""
        self._edit_data = {
            "name": self.agent.name,
            "aimodel": self.agent.aimodel.name if self.agent.aimodel else "",
            "description": self.agent.description or "",
            "priority": self.agent.priority,
            "max_turns": self.agent.max_turns,
            "max_unattended_turns": self.agent.max_unattended_turns,
            "max_retries": self.agent.max_retries,
        }
        self.update()

    def cancelEdit(self) -> None:
        """Cancel editing and return to view mode."""
        self._editing = False
        self._edit_error = ""
        self.update()

    def setField(self, field: str, value: str) -> None:
        """Set an edit field value."""
        if field in self._edit_data:
            self._edit_data[field] = value

    def saveEdit(self) -> None:
        """Save edited agent."""
        name = (self._edit_data.get("name") or "").strip()
        if not name:
            self._edit_error = "Name is required."
            self.update()
            return

        self.agent.name = name
        self.agent.description = self._edit_data.get("description", "")

        # Update priority if changed
        try:
            new_priority = int(self._edit_data.get("priority", self.agent.priority))
            self.agent.priority = max(0, min(99, new_priority))
        except (ValueError, TypeError):
            pass

        # Update max_turns if changed
        try:
            new_max_turns = int(self._edit_data.get("max_turns", self.agent.max_turns))
            if new_max_turns >= 0:
                self.agent.max_turns = new_max_turns
        except (ValueError, TypeError):
            pass

        # Update max_unattended_turns if changed
        try:
            new_max_unattended = int(self._edit_data.get("max_unattended_turns", self.agent.max_unattended_turns))
            if new_max_unattended >= 0:
                self.agent.max_unattended_turns = new_max_unattended
        except (ValueError, TypeError):
            pass

        # Update max_retries if changed
        try:
            new_max_retries = int(self._edit_data.get("max_retries", self.agent.max_retries))
            if new_max_retries >= 0:
                self.agent.max_retries = new_max_retries
        except (ValueError, TypeError):
            pass

        self.agent.save()

        self._editing = False
        self._edit_error = ""
        self.update()

    def deleteAgent(self, pk: int) -> None:
        """Delete the agent."""
        try:
            agent = AgentModel.objects.get(pk=int(pk))
            agent.delete()
            # Close this tab
            main_view = self._find_main_view()
            if main_view is not None and hasattr(main_view, "close_tab"):
                main_view.close_tab(self)
        except (AgentModel.DoesNotExist, ValueError, TypeError):
            pass