from __future__ import annotations
import json
from typing import TYPE_CHECKING, Any

from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel
from server.models.workspace import WorkspaceModel
from runtime.agents.agent import Agent
from runtime.cron.file_io import write_cron_file
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView
from ui.main.cron.cron import CronView
from ui.main.rightpanel.cron.rightpanel_cron import RightPanelCron

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


class CronCreateView(PyHtmlView):
    RIGHTPANEL_VIEW = RightPanelCron
    DOM_ELEMENT_CLASS = "main-view"
    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">New job</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Cancel" onclick="pyview.cancelCronForm()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
                <button class="panel-head-btn primary" title="Save" onclick="pyview.saveCronForm()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content">
                <form class="detail-form" onsubmit="event.preventDefault(); pyview.saveCronForm();">

                    <div class="detail-form-row">
                        <label for="cfName">Name</label>
                        <input type="text" id="cfName" value="{{ pyview._form_data.name }}" placeholder="Optional" autocomplete="off" onchange="pyview.setCronField('name', this.value)">
                    </div>

                    <div class="detail-form-row">
                        <label for="cfSchedule">Schedule</label>
                        <input type="text" id="cfSchedule" value="{{ pyview._form_data.schedule }}" placeholder="0 9 * * *  —  every 1h  —  @daily" autocomplete="off" required="" onchange="pyview.setCronField('schedule', this.value)">
                        <div class="detail-form-hint">
                            <strong>Standard cron:</strong> <code>min hour day month weekday</code> (e.g. <code>0 9 * * 1-5</code> = weekdays at 9AM) &mdash;
                            <strong>Shorthands:</strong> <code>@daily</code>, <code>@hourly</code>, <code>@weekly</code> &mdash;
                            <strong>Every N:</strong> <code>every 30m</code>, <code>every 2h</code>, <code>every 10min</code>
                        </div>
                    </div>

                    <div class="detail-form-row">
                        <label for="cfAgent">Agent</label>
                        <select id="cfAgent" onchange="pyview.onAgentChange(this.value)" required="">
                            <option value="">-- Select agent --</option>
                            {% for agent in pyview.agent_list %}
                            <option value="{{ agent.name }}"{% if pyview._form_data.agent == agent.name %} selected{% endif %}>{{ agent.name }}</option>
                            {% endfor %}
                        </select>
                    </div>

                    <div class="detail-form-row">
                        <label for="cfWorkspace">Workspace</label>
                        <select id="cfWorkspace" onchange="pyview.setCronField('workspace', this.value)">
                            <option value="">-- None --</option>
                            {% for ws in pyview.workspace_list %}
                            <option value="{{ ws.name }}"{% if pyview._form_data.workspace == ws.name %} selected{% endif %}>{{ ws.name }}</option>
                            {% endfor %}
                        </select>
                    </div>

                    <div class="detail-form-row">
                        <label>Session</label>
                        <div style="display:flex;flex-direction:column;gap:6px;width:100%">
                            <div style="display:flex;gap:12px">
                                <label style="font-weight:normal;display:flex;align-items:center;gap:4px">
                                    <input type="radio" name="cfSessionMode" value="new" onchange="pyview.setCronField('session_mode', this.value)"
                                        {% if pyview._form_data.session_mode == 'new' %}checked{% endif %}>
                                    New session each run
                                </label>
                                <label style="font-weight:normal;display:flex;align-items:center;gap:4px">
                                    <input type="radio" name="cfSessionMode" value="existing" onchange="pyview.setCronField('session_mode', this.value)"
                                        {% if pyview._form_data.session_mode == 'existing' %}checked{% endif %}>
                                    Reuse existing session
                                </label>
                            </div>
                            {% if pyview._form_data.session_mode == 'existing' %}
                            <div class="skill-picker-wrap">
                                <input type="text" id="cfSessionName" value="{{ pyview._form_data.session_name }}" placeholder="Session name (leave blank for auto-name)" autocomplete="off"
                                    oninput="pyview.searchSessions(this.value)" onchange="pyview.setCronField('session_name', this.value)">
                                {% if pyview._session_search_results %}
                                <div class="skill-picker-dropdown" style="display:block">
                                    {% for sname in pyview._session_search_results %}
                                    <div class="skill-picker-item" onclick="pyview.selectSession({{ loop.index0 }})" style="padding:6px 10px;cursor:pointer;border-bottom:1px solid var(--border2)">{{ sname }}</div>
                                    {% endfor %}
                                </div>
                                {% endif %}
                                <div class="detail-form-hint" style="margin-top:2px">Auto-name: <code>cron:{{ pyview._form_data.agent }}:{{ pyview._form_data.name }}</code></div>
                            </div>
                            {% endif %}
                        </div>
                    </div>

                    {% if pyview._form_data.agent %}
                    <div class="detail-form-row">
                        <label for="cfFunction">Function</label>
                        <select id="cfFunction" onchange="pyview.onFunctionChange(this.value)">
                            <option value="">Send message (ingest_user_message)</option>
                            {% for group_label, items in pyview.agent_functions %}
                            <optgroup label="{{ group_label }}">
                                {% for fname, ftype in items %}
                                <option value="{{ ftype }}:{{ fname }}"{% if pyview._form_data.function_type == ftype and pyview._form_data.function_name == fname %} selected{% endif %}>{{ fname }}</option>
                                {% endfor %}
                            </optgroup>
                            {% endfor %}
                        </select>
                    </div>
                    {% endif %}

                    <div class="detail-form-row">
                        <label for="cfMessage">{% if pyview._form_data.function_type %}Message (JSON){% else %}Message{% endif %}</label>
                        <textarea id="cfMessage" rows="6" placeholder="{% if pyview._form_data.function_type %}Enter JSON matching the function signature{% else %}Message text{% endif %}" onchange="pyview.setCronField('message', this.value)">{{ pyview._form_data.message }}</textarea>
                        {% if pyview._form_data.function_type and pyview._selected_function_schema %}
                        <div class="detail-form-hint" style="margin-top:4px">
                            <strong>Expected schema:</strong>
                            <pre style="font-size:11px;margin:4px 0;white-space:pre-wrap">{{ pyview._selected_function_schema }}</pre>
                        </div>
                        {% endif %}
                    </div>

                    <div id="cfError" class="detail-form-error" style="display:{% if pyview._form_error %}block{% else %}none{% endif %}">
                        {{ pyview._form_error }}
                    </div>

                </form>
            </div>
        </div>
        <div class="main-view-empty" id="taskDetailEmpty" style="display:none">
            <svg class="main-view-empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
            <div class="main-view-empty-title" data-i18n="tasks_empty_title">Select a scheduled job</div>
            <div class="main-view-empty-sub" data-i18n="tasks_empty_sub">Pick a job from the sidebar to view its details and runs, or create a new one.</div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent: Any, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._form_data: dict[str, str] = {
            "name": "",
            "schedule": "",
            "agent": "",
            "workspace": "",
            "session_mode": "new",
            "session_name": "",
            "function_type": "",
            "function_name": "",
            "message": "",
        }
        self._form_error: str = ""
        self._session_search_results: list[str] = []
        self._selected_function_schema: str = ""

    @property
    def workspace_list(self) -> list[WorkspaceModel]:
        return list(WorkspaceModel.objects.all().order_by("name"))

    @property
    def agent_list(self) -> list[AgentModel]:
        return [a for a in self.subject.agents.root() if a.is_user_visible]

    @property
    def agent_functions(self) -> list[tuple[str, list[tuple[str, str]]]]:
        name = self._form_data.get("agent", "")
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

    def setCronField(self, field: str, value: str) -> None:
        self._form_data[field] = value
        if field == "function_type":
            parts = value.split(":", 1)
            if len(parts) == 2:
                self._form_data["function_type"] = parts[0]
                self._form_data["function_name"] = parts[1]
                self._update_function_schema()
            else:
                self._form_data["function_type"] = ""
                self._form_data["function_name"] = ""
                self._selected_function_schema = ""
        if field == "function_type" and not value:
            self._form_data["function_type"] = ""
            self._form_data["function_name"] = ""
            self._selected_function_schema = ""
        self.update()

    def onAgentChange(self, agent_name: str) -> None:
        self._form_data["agent"] = agent_name
        self._form_data["function_type"] = ""
        self._form_data["function_name"] = ""
        self._selected_function_schema = ""
        self.update()

    def onFunctionChange(self, raw: str) -> None:
        self.setCronField("function_type", raw)

    def _update_function_schema(self) -> None:
        ftype = self._form_data.get("function_type", "")
        fname = self._form_data.get("function_name", "")
        if not ftype or not fname:
            self._selected_function_schema = ""
            return
        agent_name = self._form_data.get("agent", "")
        agent_model = AgentModel.objects.filter(name=agent_name).first()
        if not agent_model:
            self._selected_function_schema = ""
            return
        agent = Agent(agent_model=agent_model)
        getter = {"task": agent.get_task, "tool": agent.get_tool, "command": agent.get_command}.get(ftype)
        if not getter:
            self._selected_function_schema = ""
            return
        tdv = getter(fname)
        if tdv and tdv.function_schema:
            self._selected_function_schema = json.dumps(tdv.function_schema, indent=2)
        else:
            self._selected_function_schema = ""

    def searchSessions(self, query: str) -> None:
        if not query:
            self._session_search_results = []
        else:
            qs = SessionModel.objects.filter(name__icontains=query).values_list("name", flat=True).distinct()[:10]
            self._session_search_results = list(qs)
        self.update()

    def selectSession(self, index: int) -> None:
        if 0 <= index < len(self._session_search_results):
            self._form_data["session_name"] = self._session_search_results[index]
        self._session_search_results = []
        self.update()

    def saveCronForm(self) -> None:
        fd = self._form_data
        if not fd.get("schedule"):
            self._form_error = "Schedule is required."
            self.update()
            return
        if not fd.get("agent"):
            self._form_error = "Agent is required."
            self.update()
            return

        message_content = fd.get("message", "")
        if fd.get("function_type") and message_content:
            try:
                json.loads(message_content)
            except (ValueError, TypeError):
                self._form_error = "Message must be valid JSON when a function is selected."
                self.update()
                return

        try:  # noqa: WPS337
            ws_name = fd.get("workspace", "")
            workspace_id = None
            if ws_name:
                ws = WorkspaceModel.objects.filter(name=ws_name).first()
                if ws:
                    workspace_id = ws.pk

            created = self.subject.cronjobs.create(
                name=fd.get("name", ""),
                schedule=fd.get("schedule", ""),
                agent_id=AgentModel.objects.get(name=fd["agent"]).pk,
                description="",
                workspace_id=workspace_id,
                session_mode=fd.get("session_mode", "new"),
                session_name=fd.get("session_name", ""),
                message_content=message_content,
                function_type=fd.get("function_type", ""),
                function_name=fd.get("function_name", ""),
            )
            write_cron_file(created)
            self._form_error = ""
            parent = self._find_main_view()
            if parent:
                parent.create_and_open_tab(CronView, created)
            self.close_tab()
        except Exception as e:
            self._form_error = f"Error: {e}"
            self.update()

    def cancelCronForm(self) -> None:
        self.close_tab()

    def _find_main_view(self):
        from ui.main.main_view import MainView
        parent = self.parent
        while parent and not isinstance(parent, MainView):
            parent = parent.parent
        return parent

    def close_tab(self) -> None:
        parent = self._find_main_view()
        if parent:
            parent.close_tab(self)
