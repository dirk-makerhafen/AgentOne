from __future__ import annotations
from typing import TYPE_CHECKING, Any

from django.utils import timezone

from server.models.agents.agent import AgentModel
from runtime.agents.agent import Agent
from runtime.cron.file_io import write_cron_file, delete_cron_file, rename_cron_file
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class CronView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title" id="cronDetailTitle">
                {% if pyview._editing %}
                    <input type="text" value="{{ pyview.subject.name }}" onchange="pyview.setEditField('name', this.value)" style="font-size:inherit;width:300px">
                {% else %}
                    {{ pyview.subject.name }}
                {% endif %}
            </div>
            <div class="main-view-actions">
                {% if pyview._editing %}
                    <button class="panel-head-btn" title="Cancel" onclick="pyview.cancelEdit()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                    <button class="panel-head-btn primary" title="Save" onclick="pyview.saveEdit()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                    </button>
                {% else %}
                    <button class="panel-head-btn" title="Run now" onclick="pyview.runNow()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                    </button>
                    <button class="panel-head-btn" title="{% if pyview.subject.is_active %}Pause{% else %}Resume{% endif %}" onclick="pyview.toggleActive()">
                        {% if pyview.subject.is_active %}
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
                        {% else %}
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                        {% endif %}
                    </button>
                    <button class="panel-head-btn" title="Edit" onclick="pyview.startEdit()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                    </button>
                    <button class="panel-head-btn" title="Duplicate" onclick="pyview.duplicateCron()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    </button>
                    <button class="panel-head-btn" title="Delete" onclick="pyview.deleteCron()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"></path><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"></path><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                {% endif %}
            </div>
        </div>
        <div class="main-view-body" id="cronDetailBody">
            <div class="main-view-content">

                {% if pyview._editing %}
                {# --- Edit mode --- #}
                <div class="detail-card">
                    <div class="detail-card-title">Details</div>
                    <div class="detail-form-row">
                        <label>Schedule</label>
                        <input type="text" value="{{ pyview._edit_data.schedule }}" onchange="pyview.setEditField('schedule', this.value)" placeholder="0 9 * * *">
                        <div class="detail-form-hint" style="margin-top:2px">
                            <strong>Standard:</strong> <code>min hour day month weekday</code> &mdash;
                            <strong>Shorthand:</strong> <code>@daily</code>, <code>@hourly</code>, <code>@weekly</code> &mdash;
                            <strong>Every N:</strong> <code>every 30m</code>, <code>every 2h</code>
                        </div>
                    </div>
                    <div class="detail-form-row">
                        <label>Agent</label>
                        <select onchange="pyview.setEditField('agent', this.value)">
                            <option value="">-- Select agent --</option>
                            {% for agent in pyview.agent_list %}
                            <option value="{{ agent.name }}"{% if pyview._edit_data.agent == agent.name %} selected{% endif %}>{{ agent.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label>Workspace</label>
                        <select onchange="pyview.setEditField('workspace', this.value)">
                            <option value="">-- None --</option>
                            {% for ws in pyview.workspace_list %}
                            <option value="{{ ws.name }}"{% if pyview._edit_data.workspace == ws.name %} selected{% endif %}>{{ ws.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label>Session</label>
                        <div style="display:flex;gap:8px;flex-wrap:wrap">
                            <label style="font-weight:normal"><input type="radio" name="ceditSessionMode" value="new" onchange="pyview.setEditField('session_mode', this.value)" {% if pyview._edit_data.session_mode == 'new' %}checked{% endif %}> New each run</label>
                            <label style="font-weight:normal"><input type="radio" name="ceditSessionMode" value="existing" onchange="pyview.setEditField('session_mode', this.value)" {% if pyview._edit_data.session_mode == 'existing' %}checked{% endif %}> Reuse existing</label>
                        </div>
                        <input type="text" value="{{ pyview._edit_data.session_name }}" onchange="pyview.setEditField('session_name', this.value)" placeholder="Session name (auto if blank)" style="margin-top:4px">
                    </div>
                    <div class="detail-form-row">
                        <label>Function</label>
                        <select onchange="pyview.setEditField('function', this.value)">
                            <option value="">Send message (ingest_user_message)</option>
                            {% for group_label, items in pyview.edit_functions %}
                            <optgroup label="{{ group_label }}">
                                {% for fname, ftype in items %}
                                <option value="{{ ftype }}:{{ fname }}"{% if pyview._edit_data.function_type == ftype and pyview._edit_data.function_name == fname %} selected{% endif %}>{{ fname }}</option>
                                {% endfor %}
                            </optgroup>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label for="ceditMessage">{% if pyview._edit_data.function_type %}Message (JSON){% else %}Message{% endif %}</label>
                        <textarea id="ceditMessage" rows="4" onchange="pyview.setEditField('message', this.value)">{{ pyview._edit_data.message }}</textarea>
                    </div>
                </div>

                {% else %}
                {# --- Read-only mode --- #}
                <div class="detail-card">
                    <div class="detail-card-title">Status</div>
                    <div class="detail-row">
                        <div class="detail-row-label">Status</div>
                        <div class="detail-row-value">
                            <span class="detail-badge {% if pyview.subject.is_active %}ok{% else %}warn{% endif %}">
                                {% if pyview.subject.is_active %}active{% else %}paused{% endif %}
                            </span>
                        </div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Schedule</div>
                        <div class="detail-row-value"><code>{{ pyview.subject.schedule }}</code></div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Last run</div>
                        <div class="detail-row-value">{{ pyview.last_run_display }}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Next run</div>
                        <div class="detail-row-value">{{ pyview.next_run_display }}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Total runs</div>
                        <div class="detail-row-value">{{ pyview.subject.total_runs }}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Last status</div>
                        <div class="detail-row-value">
                            {% if pyview.subject.last_status %}
                            <span class="detail-badge {% if pyview.subject.last_status == 'success' %}ok{% else %}warn{% endif %}">
                                {{ pyview.subject.last_status }}
                            </span>
                            {% else %}
                            &mdash;
                            {% endif %}
                        </div>
                    </div>
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Configuration</div>
                    <div class="detail-row">
                        <div class="detail-row-label">Agent</div>
                        <div class="detail-row-value">{{ pyview.subject.agent.name }}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Workspace</div>
                        <div class="detail-row-value">{% if pyview.subject.workspace %}{{ pyview.subject.workspace.name }}{% else %}&mdash;{% endif %}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Session mode</div>
                        <div class="detail-row-value">{{ pyview.session_mode_display }}</div>
                    </div>
                    {% if pyview.subject.session_mode == 'existing' and pyview.subject.session_name %}
                    <div class="detail-row">
                        <div class="detail-row-label">Session name</div>
                        <div class="detail-row-value">{{ pyview.subject.session_name }}</div>
                    </div>
                    {% endif %}
                    <div class="detail-row">
                        <div class="detail-row-label">Function</div>
                        <div class="detail-row-value">
                            {% if pyview.subject.function_type and pyview.subject.function_name %}
                                <span class="detail-badge">{{ pyview.subject.function_type }}</span>
                                <code>{{ pyview.subject.function_name }}</code>
                            {% else %}
                                Send message (ingest_user_message)
                            {% endif %}
                        </div>
                    </div>
                </div>

                    <div class="detail-card">
                        <div class="detail-card-title">Message</div>
                    <div class="detail-prompt" style="white-space:pre-wrap;max-height:200px;overflow:auto">
                        {% if pyview.subject.message %}
                            {{ pyview.subject.message.content }}
                        {% else %}
                            <span style="color:var(--muted)">(empty)</span>
                        {% endif %}
                    </div>
                </div>

                <div class="detail-card" id="cronDetailRuns">
                    <div class="detail-card-title">Last output</div>
                    <div style="color:var(--muted);font-size:12px">(run history coming soon)</div>
                </div>
                {% endif %}

            </div>
        </div>
        <div class="main-view-empty" id="taskDetailEmpty" style="display:none">
            <svg class="main-view-empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            <div class="main-view-empty-title" data-i18n="tasks_empty_title">Select a scheduled job</div>
            <div class="main-view-empty-sub" data-i18n="tasks_empty_sub">Pick a job from the sidebar to view its details and runs, or create a new one.</div>
        </div>
    '''

    def __init__(self, subject: Any, parent: Any, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._editing = False
        self._edit_data: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Read-only display helpers
    # ------------------------------------------------------------------

    @property
    def workspace_list(self) -> list:
        from server.models.workspace import WorkspaceModel
        return list(WorkspaceModel.objects.all().order_by("name"))

    @property
    def agent_list(self) -> list[AgentModel]:
        return list(AgentModel.objects.all().order_by("name"))

    @property
    def last_run_display(self) -> str:
        if self.subject.last_run_at:
            local = timezone.localtime(self.subject.last_run_at)
            return local.strftime("%Y-%m-%d %H:%M:%S")
        return "never"

    @property
    def next_run_display(self) -> str:
        if self.subject.next_run_at:
            local = timezone.localtime(self.subject.next_run_at)
            return local.strftime("%Y-%m-%d %H:%M:%S")
        from runtime.cron.execute import compute_next_run
        nxt = compute_next_run(self.subject.schedule)
        if nxt:
            return f"{nxt.strftime('%Y-%m-%d %H:%M:%S')} (estimated)"
        return "—"

    @property
    def session_mode_display(self) -> str:
        if self.subject.session_mode == "new":
            return "New session each run"
        return "Reuse existing session"

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def runNow(self) -> None:
        from runtime.cron.execute import execute_cron_job
        execute_cron_job(self.subject.pk)

    def toggleActive(self) -> None:
        self.subject.is_active = not self.subject.is_active
        self.subject.save(update_fields=["is_active"])
        self.update()

    def deleteCron(self) -> None:
        delete_cron_file(self.subject.name)
        self.subject.delete()
        self._close_tab()

    def duplicateCron(self) -> None:
        from ui.main.cron.create import CronCreateView
        parent = self._find_main_view()
        if parent:
            parent.create_and_open_tab(CronCreateView, self.subject)

    def startEdit(self) -> None:
        self._editing = True
        m = self.subject.message
        self._edit_data = {
            "name": self.subject.name,
            "schedule": self.subject.schedule,
            "agent": self.subject.agent.name if self.subject.agent else "",
            "workspace": self.subject.workspace.name if self.subject.workspace else "",
            "session_mode": self.subject.session_mode or "new",
            "session_name": self.subject.session_name or "",
            "function_type": self.subject.function_type or "",
            "function_name": self.subject.function_name or "",
            "function": f"{self.subject.function_type}:{self.subject.function_name}" if self.subject.function_type else "",
            "message": m.content if m else "",
        }
        self.update()

    def cancelEdit(self) -> None:
        self._editing = False
        self.update()

    def setEditField(self, field: str, value: str) -> None:
        if field == "function":
            parts = value.split(":", 1)
            if len(parts) == 2:
                self._edit_data["function_type"] = parts[0]
                self._edit_data["function_name"] = parts[1]
            else:
                self._edit_data["function_type"] = ""
                self._edit_data["function_name"] = ""
        else:
            self._edit_data[field] = value
        self.update()

    def saveEdit(self) -> None:
        d = self._edit_data

        agent = None
        if d.get("agent"):
            agent = AgentModel.objects.filter(name=d["agent"]).first()

        from server.models.content import GenericContent
        message_content = d.get("message", "")
        message = self.subject.message
        if message_content:
            if message:
                message.content = message_content
                message.save(update_fields=["content"])
            else:
                message = GenericContent.from_text(message_content)
        elif message:
            message.delete()
            message = None

        old_name = self.subject.name
        new_name = d.get("name", old_name)
        self.subject.name = new_name
        new_schedule = d.get("schedule", self.subject.schedule)
        if new_schedule != self.subject.schedule:
            from runtime.cron.execute import compute_next_run
            self.subject.schedule = new_schedule
            self.subject.next_run_at = compute_next_run(new_schedule)
        if agent:
            self.subject.agent = agent

        ws_name = d.get("workspace", "")
        if ws_name:
            from server.models.workspace import WorkspaceModel
            ws = WorkspaceModel.objects.filter(name=ws_name).first()
            self.subject.workspace = ws
        else:
            self.subject.workspace = None

        self.subject.session_mode = d.get("session_mode", "new")
        self.subject.session_name = d.get("session_name", "")
        self.subject.function_type = d.get("function_type", "")
        self.subject.function_name = d.get("function_name", "")
        self.subject.message = message
        self.subject.save()

        if new_name != old_name:
            rename_cron_file(old_name, new_name)
        write_cron_file(self.subject)

        self._editing = False
        self.update()

    @property
    def edit_functions(self) -> list[tuple[str, list[tuple[str, str]]]]:
        name = self._edit_data.get("agent", "")
        if not name:
            return []
        agent_model = AgentModel.objects.filter(name=name).first()
        if not agent_model:
            return []
        agent = Agent(agent_model=agent_model)
        groups: list[tuple[str, list[tuple[str, str]]]] = []
        tasks = [(tdv.task_definition.name, "task") for tdv in agent.allowedTasks]
        if tasks:
            groups.append(("Tasks", tasks))
        tools = [(tdv.task_definition.name, "tool") for tdv in agent.allowedTools]
        if tools:
            groups.append(("Tools", tools))
        commands = [(tdv.task_definition.name, "command") for tdv in agent.allowedCommands]
        if commands:
            groups.append(("Commands", commands))
        return groups

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent

    def _close_tab(self):
        parent = self._find_main_view()
        if parent and hasattr(parent, "close_tab"):
            parent.close_tab(self)
