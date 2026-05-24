"""Create consumer form — wires a consumer TaskDefinitionVersion to a named pipe."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from runtime.agents.agent import Agent
from server.models.agents.agent import AgentModel
from server.models.pipe import NamedPipe, NamedPipeSubscription
from server.models.tasks.task_definition_version import TaskDefinitionVersion
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.app import UiApp
    from ui.main.main_view import MainView


class PipeCreateView(ModelView):
    """Create a new NamedPipe (name + description).

    Subject is a ``UiApp`` instance.
    """

    DOM_ELEMENT_CLASS = "main-view"

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">New pipe</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Cancel" onclick="pyview.cancel()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
                <button class="panel-head-btn primary" title="Save" onclick="pyview.savePipe()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content">
                <div class="detail-card">
                    <div class="detail-card-title">Pipe</div>

                    <div class="detail-form-row">
                        <label>Name</label>
                        <input type="text" value="{{ pyview._form_data.name }}" onchange="pyview.setField('name', this.value)" placeholder="my-pipe-name">
                    </div>

                    <div class="detail-form-row">
                        <label>Description</label>
                        <input type="text" value="{{ pyview._form_data.description }}" onchange="pyview.setField('description', this.value)" placeholder="Optional description">
                    </div>

                    {% if pyview._form_error %}
                    <div style="color:red;padding:8px;background:var(--danger-bg);border-radius:4px;margin-top:8px">
                        {{ pyview._form_error }}
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._form_data: dict[str, str] = {
            "name": "",
            "description": "",
        }
        self._form_error = ""

    def setField(self, field: str, value: str) -> None:
        self._form_data[field] = value
        self._form_error = ""
        self.update()

    def savePipe(self) -> None:
        name = self._form_data.get("name", "").strip()
        if not name:
            self._form_error = "Pipe name is required."
            self.update()
            return
        description = self._form_data.get("description", "").strip()
        try:
            NamedPipe.objects.create(name=name, description=description)
        except Exception as e:
            self._form_error = f"Failed to create pipe: {e}"
            self.update()
            return
        self._close_tab()

    def cancel(self) -> None:
        self._close_tab()

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent

    def _close_tab(self) -> None:
        parent = self._find_main_view()
        if parent and hasattr(parent, "close_tab"):
            parent.close_tab(self)


class PipeSubscriptionCreateView(ModelView):
    """Create a new pipe consumer.

    Subject is a ``UiApp`` instance (like CronCreateView).
    Use ``prefill_pipe_pk`` class attribute to pre-select a pipe
    when opening from a pipe detail view.
    """

    prefill_pipe_pk: int | None = None

    DOM_ELEMENT_CLASS = "main-view"

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">New consumer</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Cancel" onclick="pyview.cancel()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
                <button class="panel-head-btn primary" title="Save" onclick="pyview.saveSubscription()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content">

                <div class="detail-card">
                    <div class="detail-card-title">Subscription</div>

                    <div class="detail-form-row">
                        <label>Name</label>
                        <input type="text" value="{{ pyview._form_data.name }}" onchange="pyview.setField('name', this.value)" placeholder="process emails">
                    </div>

                    <div class="detail-form-row">
                        <label>Pipe</label>
                        <select onchange="pyview.setField('pipe', this.value)">
                            <option value="">Select an existing pipe...</option>
                            {% for pipe in pyview.pipe_list %}
                            <option value="{{ pipe.pk }}"{% if pyview._form_data.pipe == pipe.pk|string() %} selected{% endif %}>
                                {{ pipe.name }}{% if pipe.description %} &mdash; {{ pipe.description }}{% endif %}
                            </option>
                            {% endfor %}
                        </select>
                    </div>

                    <div class="detail-form-row">
                        <label>Or new pipe name</label>
                        <input type="text" value="{{ pyview._form_data.new_pipe_name }}" onchange="pyview.setField('new_pipe_name', this.value)" placeholder="my-new-pipe (creates if not exists)">
                        <div class="detail-form-hint">Type a name to create a new pipe. Leave empty to use the dropdown selection above.</div>
                    </div>

                    <div class="detail-form-row">
                        <label>Agent</label>
                        <select onchange="pyview.setField('agent', this.value)">
                            <option value="">-- Select agent --</option>
                            {% for agent in pyview.agent_list %}
                            <option value="{{ agent.pk }}"{% if pyview._form_data.agent == agent.pk|string() %} selected{% endif %}>{{ agent.name }}</option>
                            {% endfor %}
                        </select>
                    </div>

                    <div class="detail-form-row">
                        <label>Consumer task</label>
                        {% if pyview.agent_task_groups %}
                        <select onchange="pyview.setField('consumer_task', this.value)">
                            <option value="">Select a task...</option>
                            {% for group_label, tdvs in pyview.agent_task_groups %}
                            <optgroup label="{{ group_label }}">
                                {% for tdv in tdvs %}
                                <option value="{{ tdv.pk }}"{% if pyview._form_data.consumer_task == tdv.pk|string() %} selected{% endif %}>
                                    {{ tdv.task_definition.name if tdv.task_definition else tdv.pk }}
                                </option>
                                {% endfor %}
                            </optgroup>
                            {% endfor %}
                        </select>
                        {% else %}
                        <select onchange="pyview.setField('consumer_task', this.value)">
                            <option value="">Select a task...</option>
                            {% for tdv in pyview.task_list %}
                            <option value="{{ tdv.pk }}"{% if pyview._form_data.consumer_task == tdv.pk|string() %} selected{% endif %}>
                                {{ tdv.task_definition.name if tdv.task_definition else tdv.pk }}
                                {% if tdv.description %} &mdash; {{ tdv.description[:60] }}{% endif %}
                            </option>
                            {% endfor %}
                        </select>
                        {% endif %}
                        <div class="detail-form-hint">Filtered by selected agent's allowed tasks, tools, and commands.</div>
                    </div>

                    <div class="detail-form-row">
                        <label>Session</label>
                        <div style="display:flex;flex-direction:column;gap:6px;width:100%">
                            <div style="display:flex;gap:12px">
                                <label style="font-weight:normal;display:flex;align-items:center;gap:4px">
                                    <input type="radio" name="psSessionMode" value="new" onchange="pyview.setField('session_mode', this.value)"
                                        {% if pyview._form_data.session_mode == 'new' %}checked{% endif %}>
                                    New session each run
                                </label>
                                <label style="font-weight:normal;display:flex;align-items:center;gap:4px">
                                    <input type="radio" name="psSessionMode" value="existing" onchange="pyview.setField('session_mode', this.value)"
                                        {% if pyview._form_data.session_mode == 'existing' %}checked{% endif %}>
                                    Reuse existing session
                                </label>
                            </div>
                            {% if pyview._form_data.session_mode == 'existing' %}
                            <input type="text" value="{{ pyview._form_data.session_name }}" onchange="pyview.setField('session_name', this.value)" placeholder="Session name (leave blank for auto-name)">
                            <div class="detail-form-hint">Auto-name: <code>pipe:&lt;pipe-name&gt;</code></div>
                            {% endif %}
                        </div>
                    </div>

                    <div class="detail-form-row">
                        <label>Active</label>
                        <label style="font-weight:normal">
                            <input type="checkbox" onchange="pyview.setField('is_active', this.checked ? 'true' : 'false')"
                                {% if pyview._form_data.is_active == 'true' %}checked{% endif %}>
                            Enable consumer
                        </label>
                    </div>

                    <div class="detail-form-row">
                        <label>Args template (JSON)</label>
                        <textarea rows="3" onchange="pyview.setField('arguments_template', this.value)" placeholder='{"extra_param": "value"}' style="font-family:monospace;font-size:12px">{{ pyview._form_data.arguments_template }}</textarea>
                        <div class="detail-form-hint">Extra arguments merged into every dispatched call.</div>
                    </div>

                    {% if pyview._form_error %}
                    <div style="color:red;padding:8px;background:var(--danger-bg);border-radius:4px;margin-top:8px">
                        {{ pyview._form_error }}
                    </div>
                    {% endif %}
                </div>

            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        prefill = str(self.__class__.prefill_pipe_pk or "")
        self.__class__.prefill_pipe_pk = None  # consume once
        self._form_data: dict[str, str] = {
            "name": "",
            "pipe": prefill,
            "new_pipe_name": "",
            "consumer_task": "",
            "agent": "",
            "session_mode": "new",
            "session_name": "",
            "is_active": "true",
            "arguments_template": "{}",
        }
        self._form_error = ""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def pipe_list(self) -> list[NamedPipe]:
        return list(NamedPipe.objects.all().order_by("name"))

    @property
    def task_list(self) -> list[TaskDefinitionVersion]:
        return list(
            TaskDefinitionVersion.objects.select_related("task_definition")
            .all().order_by("pk")[:200]
        )

    @property
    def agent_list(self) -> list[AgentModel]:
        return list(AgentModel.objects.all().order_by("name"))

    @property
    def agent_task_groups(self) -> list[tuple[str, list[TaskDefinitionVersion]]]:
        agent_pk = self._form_data.get("agent", "").strip()
        if not agent_pk:
            return []
        try:
            agent_model = AgentModel.objects.get(pk=agent_pk)
        except (AgentModel.DoesNotExist, ValueError):
            return []
        agent = Agent(agent_model=agent_model)
        groups: list[tuple[str, list[TaskDefinitionVersion]]] = []
        tasks = list(agent.allowedTasks)
        if tasks:
            groups.append(("Tasks", tasks))
        tools = list(agent.allowedTools)
        if tools:
            groups.append(("Tools", tools))
        commands = list(agent.allowedCommands)
        if commands:
            groups.append(("Commands", commands))
        return groups

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def setField(self, field: str, value: str) -> None:
        self._form_data[field] = value
        self._form_error = ""
        if field == "agent":
            self._form_data["consumer_task"] = ""
        self.update()

    def saveSubscription(self) -> None:
        d = self._form_data
        self._form_error = ""

        pipe_pk = d.get("pipe", "")
        new_pipe_name = d.get("new_pipe_name", "").strip()
        task_pk = d.get("consumer_task", "")

        if not pipe_pk and not new_pipe_name:
            self._form_error = "Please select an existing pipe or enter a new pipe name."
            self.update()
            return
        if not task_pk:
            self._form_error = "Please select a consumer task."
            self.update()
            return

        if new_pipe_name:
            pipe, _ = NamedPipe.objects.get_or_create(name=new_pipe_name)
        else:
            try:
                pipe = NamedPipe.objects.get(pk=pipe_pk)
            except NamedPipe.DoesNotExist:
                self._form_error = "Selected pipe not found."
                self.update()
                return

        try:
            consumer = TaskDefinitionVersion.objects.get(pk=task_pk)
        except TaskDefinitionVersion.DoesNotExist:
            self._form_error = "Selected consumer task not found."
            self.update()
            return

        agent_pk = d.get("agent", "").strip()
        agent = None
        if agent_pk:
            try:
                agent = AgentModel.objects.get(pk=agent_pk)
            except AgentModel.DoesNotExist:
                self._form_error = "Selected agent not found."
                self.update()
                return

        import json
        args_template = {}
        raw_args = d.get("arguments_template", "{}").strip()
        if raw_args:
            try:
                args_template = json.loads(raw_args)
                if not isinstance(args_template, dict):
                    self._form_error = "Args template must be a JSON object."
                    self.update()
                    return
            except json.JSONDecodeError as e:
                self._form_error = f"Invalid JSON: {e}"
                self.update()
                return

        try:
            NamedPipeSubscription.objects.create(
                pipe=pipe,
                consumer_task=consumer,
                name=d.get("name", ""),
                agent=agent,
                session_mode=d.get("session_mode", "new"),
                session_name=d.get("session_name", ""),
                is_active=d.get("is_active") == "true",
                arguments_template=args_template,
            )
        except Exception as e:
            self._form_error = f"Failed to create consumer: {e}"
            self.update()
            return

        self._close_tab()

    def cancel(self) -> None:
        self._close_tab()

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent

    def _close_tab(self) -> None:
        parent = self._find_main_view()
        if parent and hasattr(parent, "close_tab"):
            parent.close_tab(self)
