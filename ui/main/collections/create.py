"""Create a DataCollection (stream or ordered set)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.models.agents.agent import AgentModel
from server.models.collections import DataCollection
from runtime.agents.agent import Agent
from ui.lib.model_view import ModelView
from ui.lib.pyHtmlGui.pyhtmlgui.view.pyhtml_view import PyHtmlView

if TYPE_CHECKING:
    from ui.app import UiApp


class CollectionCreateView(PyHtmlView):
    
    """Create a new DataCollection (stream or set)."""

    DOM_ELEMENT_CLASS = "main-view"

    TEMPLATE_STR = '''
        <script>
            function filterSourceList(inputId, listId) {
                var val = document.getElementById(inputId).value.toLowerCase();
                var list = document.getElementById(listId);
                for (var i = 0; i < list.children.length; i++) {
                    var item = list.children[i];
                    item.style.display = item.textContent.toLowerCase().includes(val) ? "" : "none";
                }
            }
        </script>
        <div class="main-view-header">
            <div class="main-view-title">New data flow</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="Cancel" onclick="pyview.cancel()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
                <button class="panel-head-btn primary" title="Save" onclick="pyview.save()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content">

                <div class="detail-card">
                    <div class="detail-card-title">Data collection</div>
                    <div class="detail-form-row">
                        <label>Name</label>
                        <input type="text" value="{{ pyview._form_data.name }}" onchange="pyview.setField('name', this.value)" placeholder="my-stream-or-set">
                    </div>
                    <div class="detail-form-row">
                        <label>Description</label>
                        <input type="text" value="{{ pyview._form_data.description }}" onchange="pyview.setField('description', this.value)" placeholder="Optional description">
                    </div>
                    <div class="detail-form-row">
                        <label>Type</label>
                        <select onchange="pyview.onTypeChange(this.value)">
                            <option value="stream"{% if pyview._form_data.collection_type == 'stream' %} selected{% endif %}>Stream (append-only)</option>
                            <option value="set"{% if pyview._form_data.collection_type == 'set' %} selected{% endif %}>Ordered Set (mutable)</option>
                        </select>
                    </div>
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">
                        Sources
                        <button class="panel-head-btn" onclick="pyview.addSource()" title="Add source" style="font-size:11px;padding:2px 8px;margin-left:8px">+ Add</button>
                    </div>
                    {% if pyview.source_entries %}
                        {% for src in pyview.source_entries %}
                        <div style="border:1px solid var(--border);border-radius:4px;padding:8px;margin-bottom:8px">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                                <span style="font-weight:600;font-size:12px">Source {{ loop.index }}</span>
                                <button onclick="pyview.removeSource('{{ src.uid }}')" style="border:none;background:none;color:var(--danger);cursor:pointer;font-size:16px" title="Remove source">&times;</button>
                            </div>
                            <div class="detail-form-row">
                                <label>Type</label>
                                <select onchange="pyview.onSourceTypeChange('{{ src.uid }}', this.value)">
                                    <option value="query"{% if src.type == 'query' %} selected{% endif %}>Query (agent call match)</option>
                                    <option value="stream"{% if src.type == 'stream' %} selected{% endif %}>Stream</option>
                                    <option value="set"{% if src.type == 'set' %} selected{% endif %}>Ordered Set</option>
                                </select>
                            </div>
                            {% if src.type == 'query' %}
                            <div class="detail-form-row">
                                <label>Project</label>
                                <select onchange="pyview.setSourceField('{{ src.uid }}', 'project', this.value)">
                                    <option value="">-- Any project --</option>
                                    {% for p in pyview.project_list %}
                                    <option value="{{ p.name }}"{% if src.project == p.name %} selected{% endif %}>{{ p.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            <div class="detail-form-row" style="flex-direction:column;align-items:stretch">
                                <label>Agent(s)</label>
                                <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px">
                                    {% for val in src.agent_values %}
                                    <span style="display:inline-flex;align-items:center;gap:2px;background:var(--accent-bg);color:var(--accent-fg);padding:1px 6px;border-radius:3px;font-size:11px;font-family:monospace">
                                        {{ val }}
                                        <button onclick="pyview.removeSourceValue('{{ src.uid }}','agent_values','{{ val }}')" style="border:none;background:none;cursor:pointer;padding:0;font-size:14px;line-height:1;color:inherit" title="Remove">&times;</button>
                                    </span>
                                    {% endfor %}
                                </div>
                                <input id="agent_filter_{{src.uid}}" class="source-filter-input" placeholder="Filter agents..." oninput="filterSourceList('agent_filter_{{src.uid}}','agent_list_{{src.uid}}')">
                                <div id="agent_list_{{src.uid}}" class="source-option-list">
                                    {% for a in pyview.agent_list %}
                                    <div class="filter-option-item" onclick="pyview.addSourceValue('{{ src.uid }}','agent_values','{{ a.name }}');document.getElementById('agent_filter_{{src.uid}}').value='';filterSourceList('agent_filter_{{src.uid}}','agent_list_{{src.uid}}')">{{ a.name }}</div>
                                    {% endfor %}
                                </div>
                            </div>
                            <div class="detail-form-row" style="flex-direction:column;align-items:stretch">
                                <label>Function(s)</label>
                                <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px">
                                    {% for val in src.function_values %}
                                    <span style="display:inline-flex;align-items:center;gap:2px;background:var(--accent-bg);color:var(--accent-fg);padding:1px 6px;border-radius:3px;font-size:11px;font-family:monospace">
                                        {{ val }}
                                        <button onclick="pyview.removeSourceValue('{{ src.uid }}','function_values','{{ val }}')" style="border:none;background:none;cursor:pointer;padding:0;font-size:14px;line-height:1;color:inherit" title="Remove">&times;</button>
                                    </span>
                                    {% endfor %}
                                </div>
                                <input id="func_filter_{{src.uid}}" class="source-filter-input" placeholder="Filter functions..." oninput="filterSourceList('func_filter_{{src.uid}}','func_list_{{src.uid}}')">
                                <div id="func_list_{{src.uid}}" class="source-option-list">
                                    {% for f in pyview.get_function_names_for_source(src.uid) %}
                                    <div class="filter-option-item" onclick="pyview.addSourceValue('{{ src.uid }}','function_values','{{ f }}');document.getElementById('func_filter_{{src.uid}}').value='';filterSourceList('func_filter_{{src.uid}}','func_list_{{src.uid}}')">{{ f }}</div>
                                    {% endfor %}
                                </div>
                            </div>
                            <div class="detail-form-row" style="flex-direction:column;align-items:stretch">
                                <label>Session(s)</label>
                                <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px">
                                    {% for val in src.session_values %}
                                    <span style="display:inline-flex;align-items:center;gap:2px;background:var(--accent-bg);color:var(--accent-fg);padding:1px 6px;border-radius:3px;font-size:11px;font-family:monospace">
                                        {{ val }}
                                        <button onclick="pyview.removeSourceValue('{{ src.uid }}','session_values','{{ val }}')" style="border:none;background:none;cursor:pointer;padding:0;font-size:14px;line-height:1;color:inherit" title="Remove">&times;</button>
                                    </span>
                                    {% endfor %}
                                </div>
                                <input id="sess_filter_{{src.uid}}" class="source-filter-input" placeholder="Filter sessions..." oninput="filterSourceList('sess_filter_{{src.uid}}','sess_list_{{src.uid}}')">
                                <div class="source-hint-row">
                                    <span class="source-hint">Leave empty to match any</span>
                                </div>
                                <div id="sess_list_{{src.uid}}" class="source-option-list--short">
                                    <div class="filter-option-item" onclick="pyview.addSourceValue('{{ src.uid }}','session_values','default');document.getElementById('sess_filter_{{src.uid}}').value='';filterSourceList('sess_filter_{{src.uid}}','sess_list_{{src.uid}}')">default</div>
                                    {% for s in pyview.get_session_names_for_source(src.uid) %}
                                    <div class="filter-option-item" onclick="pyview.addSourceValue('{{ src.uid }}','session_values','{{ s }}');document.getElementById('sess_filter_{{src.uid}}').value='';filterSourceList('sess_filter_{{src.uid}}','sess_list_{{src.uid}}')">{{ s }}</div>
                                    {% endfor %}
                                </div>
                            </div>
                            {% elif src.type == 'stream' %}
                            <div class="detail-form-row">
                                <label>Stream</label>
                                <select onchange="pyview.setSourceField('{{ src.uid }}', 'stream', this.value)">
                                    <option value="">-- Select stream --</option>
                                    {% for dc in pyview.stream_list %}
                                    <option value="{{ dc.name }}"{% if src.stream == dc.name %} selected{% endif %}>{{ dc.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            {% elif src.type == 'set' %}
                            <div class="detail-form-row">
                                <label>Set</label>
                                <select onchange="pyview.setSourceField('{{ src.uid }}', 'set', this.value)">
                                    <option value="">-- Select set --</option>
                                    {% for dc in pyview.set_list %}
                                    <option value="{{ dc.name }}"{% if src.set == dc.name %} selected{% endif %}>{{ dc.name }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            {% endif %}
                        </div>
                        {% endfor %}
                    {% else %}
                        <div style="padding:8px;color:var(--muted);text-align:center">
                            No sources configured. Click <strong>+ Add</strong> to add a source.
                        </div>
                    {% endif %}
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Processor</div>
                    <div class="detail-form-row">
                        <label>Agent</label>
                        <select onchange="pyview.onProcessorAgentChange(this.value)">
                            <option value="">-- Select agent --</option>
                            {% for agent in pyview.agent_list %}
                            <option value="{{ agent.name }}"{% if pyview._form_data.processor_agent == agent.name %} selected{% endif %}>{{ agent.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label>Function</label>
                        <select onchange="pyview.setField('processor_function', this.value)">
                            <option value="">-- Select function --</option>
                            {% for tname in pyview.processor_functions %}
                            <option value="{{ tname }}"{% if pyview._form_data.processor_function == tname %} selected{% endif %}>{{ tname }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label>Session</label>
                        <input type="text" value="{{ pyview._form_data.processor_session }}" onchange="pyview.setField('processor_session', this.value)" placeholder="default (or {source_agent.name} template)">
                    </div>
                </div>

                {% if pyview._form_data.collection_type == 'set' %}
                <div class="detail-card">
                    <div class="detail-card-title">Set configuration</div>
                    <div class="detail-form-row">
                        <label>Member field</label>
                        <input type="text" value="{{ pyview._form_data.member_field }}" onchange="pyview.setField('member_field', this.value)" placeholder="item.get('session', 'unknown')">
                    </div>
                    <div class="detail-form-row">
                        <label>Score field</label>
                        <input type="text" value="{{ pyview._form_data.score_field }}" onchange="pyview.setField('score_field', this.value)" placeholder="float(item.get('timestamp', 0))">
                    </div>
                    <div style="margin-top:8px">
                        <div class="detail-card-title">On removed handler</div>
                    </div>
                    <div class="detail-form-row">
                        <label>Agent</label>
                        <select onchange="pyview.onRemovedAgentChange(this.value)">
                            <option value="">-- Select agent --</option>
                            {% for agent in pyview.agent_list %}
                            <option value="{{ agent.name }}"{% if pyview._form_data.on_removed_agent == agent.name %} selected{% endif %}>{{ agent.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label>Function</label>
                        <select onchange="pyview.setField('on_removed_function', this.value)">
                            <option value="">-- Select function --</option>
                            {% for tname in pyview.on_removed_functions %}
                            <option value="{{ tname }}"{% if pyview._form_data.on_removed_function == tname %} selected{% endif %}>{{ tname }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label>Session</label>
                        <input type="text" value="{{ pyview._form_data.on_removed_session }}" onchange="pyview.setField('on_removed_session', this.value)" placeholder="default">
                    </div>
                </div>
                {% endif %}

                <div class="detail-card">
                    <div class="detail-card-title">Reprocess settings</div>
                    <div class="detail-form-row">
                        <label>Retroactive on source change</label>
                        <input type="number" value="{{ pyview._form_data.retroactive_on_source_change }}" onchange="pyview.setField('retroactive_on_source_change', this.value)" placeholder="0 = off" style="width:100px">
                    </div>
                    <div class="detail-form-row">
                        <label>Max reprocess</label>
                        <input type="number" value="{{ pyview._form_data.max_reprocess }}" onchange="pyview.setField('max_reprocess', this.value)" placeholder="0 = off" style="width:100px">
                    </div>
                </div>

                {% if pyview._form_error %}
                <div style="color:red;padding:8px;background:var(--danger-bg);border-radius:4px;margin-top:8px">
                    {{ pyview._form_error }}
                </div>
                {% endif %}

            </div>
        </div>
    '''

    def __init__(self, subject: UiApp, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._form_data: dict[str, str] = {
            "name": "",
            "description": "",
            "collection_type": "stream",
            "processor_agent": "",
            "processor_function": "",
            "processor_session": "",
            "member_field": "",
            "score_field": "",
            "on_removed_agent": "",
            "on_removed_function": "",
            "on_removed_session": "",
            "retroactive_on_source_change": "0",
            "max_reprocess": "0",
        }
        self._form_error = ""
        self._source_uid_counter = 0
        self._source_entries: list[dict] = []

    # ------------------------------------------------------------------
    # List data
    # ------------------------------------------------------------------

    @property
    def agent_list(self):
        return [a for a in AgentModel.objects.all().order_by("name") if a.is_user_visible]

    @property
    def project_list(self):
        from server.models.project import Project
        return list(Project.objects.all().order_by("name"))

    @property
    def stream_list(self):
        return list(DataCollection.objects.filter(collection_type="stream").order_by("name"))

    @property
    def set_list(self):
        return list(DataCollection.objects.filter(collection_type="set").order_by("name"))

    # ------------------------------------------------------------------
    # Source entries
    # ------------------------------------------------------------------

    @property
    def all_function_names(self):
        names = set()
        for agent_model in AgentModel.objects.all():
            try:
                if not agent_model.latest_agent_version:
                    continue
                agent = Agent(agent_model=agent_model)
                for tdv in agent.allowedTasks:
                    names.add(tdv.task_definition.name)
                for tdv in agent.allowedTools:
                    names.add(tdv.task_definition.name)
                for tdv in agent.allowedCommands:
                    names.add(tdv.task_definition.name)
            except Exception:
                pass
        if not names:
            from server.models.tasks.task_definition import TaskDefinition
            names = set(TaskDefinition.objects.values_list("name", flat=True))
        return sorted(names)

    def get_session_names_for_source(self, src_uid: str) -> list[str]:
        src = next((e for e in self._source_entries if e["uid"] == src_uid), None)
        if not src:
            return self.session_names_list
        agent_names = src.get("agent_values", [])
        if not agent_names:
            return self.session_names_list
        from server.models.sessions.session_version import SessionVersionModel
        names = list(
            SessionVersionModel.objects
            .filter(agent__name__in=agent_names)
            .values_list("session__name", flat=True)
            .distinct()
            .order_by("session__name")[:50]
        )
        return names if names else self.session_names_list

    def get_function_names_for_source(self, src_uid: str) -> list[str]:
        src = next((e for e in self._source_entries if e["uid"] == src_uid), None)
        if not src:
            return self.all_function_names
        agent_names = src.get("agent_values", [])
        if not agent_names:
            return self.all_function_names
        names = set()
        for agent_model in AgentModel.objects.filter(name__in=agent_names):
            try:
                if not agent_model.latest_agent_version:
                    continue
                agent = Agent(agent_model=agent_model)
                for tdv in agent.allowedTasks:
                    names.add(tdv.task_definition.name)
                for tdv in agent.allowedTools:
                    names.add(tdv.task_definition.name)
                for tdv in agent.allowedCommands:
                    names.add(tdv.task_definition.name)
            except Exception:
                pass
        return sorted(names) if names else self.all_function_names

    @property
    def session_names_list(self):
        from server.models.sessions.session import SessionModel
        return list(SessionModel.objects.values_list("name", flat=True).distinct().order_by("name")[:50])


    @property
    def source_entries(self):
        return self._source_entries

    def addSource(self) -> None:
        uid = f"src_{self._source_uid_counter}"
        self._source_uid_counter += 1
        self._source_entries.append({"uid": uid, "type": "query", "project": "", "agent_values": [], "function_values": [], "session_values": []})
        self.update()

    def removeSource(self, uid: str) -> None:
        self._source_entries = [e for e in self._source_entries if e["uid"] != uid]
        self.update()

    def setSourceField(self, uid: str, field: str, value: str) -> None:
        for entry in self._source_entries:
            if entry["uid"] == uid:
                entry[field] = value
                break
        self.update()

    def addSourceValue(self, uid: str, field: str, value: str) -> None:
        if not value:
            return
        for entry in self._source_entries:
            if entry["uid"] == uid:
                if value not in entry.setdefault(field, []):
                    entry[field].append(value)
                break
        self.update()

    def removeSourceValue(self, uid: str, field: str, value: str) -> None:
        for entry in self._source_entries:
            if entry["uid"] == uid:
                lst = entry.get(field, [])
                if value in lst:
                    lst.remove(value)
                break
        self.update()

    def onSourceTypeChange(self, uid: str, new_type: str) -> None:
        for entry in self._source_entries:
            if entry["uid"] == uid:
                entry.clear()
                entry["uid"] = uid
                entry["type"] = new_type
                if new_type == "query":
                    entry.update({"project": "", "agent_values": [], "function_values": [], "session_values": []})
                elif new_type == "stream":
                    entry["stream"] = ""
                elif new_type == "set":
                    entry["set"] = ""
                break
        self.update()

    # ------------------------------------------------------------------
    # Processor agent/function cascading
    # ------------------------------------------------------------------

    def _agent_function_names(self, agent_name: str) -> list[str]:
        if not agent_name:
            return []
        agent_model = AgentModel.objects.filter(name=agent_name).first()
        if not agent_model or not agent_model.latest_agent_version:
            return []
        try:
            agent = Agent(agent_model=agent_model)
            names = set()
            for tdv in agent.allowedTasks:
                names.add(tdv.task_definition.name)
            for tdv in agent.allowedTools:
                names.add(tdv.task_definition.name)
            for tdv in agent.allowedCommands:
                names.add(tdv.task_definition.name)
            return sorted(names)
        except Exception:
            return []

    @property
    def processor_functions(self):
        return self._agent_function_names(self._form_data.get("processor_agent", ""))

    @property
    def on_removed_functions(self):
        return self._agent_function_names(self._form_data.get("on_removed_agent", ""))

    def onTypeChange(self, value: str) -> None:
        self._form_data["collection_type"] = value
        self._form_error = ""
        self.update()

    def onProcessorAgentChange(self, agent_name: str) -> None:
        self._form_data["processor_agent"] = agent_name
        self._form_data["processor_function"] = ""
        self._form_error = ""
        self.update()

    def onRemovedAgentChange(self, agent_name: str) -> None:
        self._form_data["on_removed_agent"] = agent_name
        self._form_data["on_removed_function"] = ""
        self._form_error = ""
        self.update()

    def setField(self, field: str, value: str) -> None:
        self._form_data[field] = value
        self._form_error = ""
        self.update()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _build_sources(self) -> list:
        result = []
        for entry in self._source_entries:
            t = entry["type"]
            if t == "query":
                src = {"type": "query"}
                if entry.get("project"):
                    src["project"] = entry["project"]
                agents = entry.get("agent_values", [])
                if agents:
                    src["agent"] = agents if len(agents) > 1 else agents[0]
                functions = entry.get("function_values", [])
                if functions:
                    src["function"] = functions if len(functions) > 1 else functions[0]
                sessions = entry.get("session_values", [])
                if sessions:
                    src["session"] = sessions if len(sessions) > 1 else sessions[0]
                result.append(src)
            elif t == "stream":
                name = entry.get("stream", "").strip()
                if name:
                    result.append({"type": "stream", "stream": name})
            elif t == "set":
                name = entry.get("set", "").strip()
                if name:
                    result.append({"type": "set", "set": name})
        return result

    def save(self) -> None:
        name = self._form_data.get("name", "").strip()
        if not name:
            self._form_error = "Name is required."
            self.update()
            return
        collection_type = self._form_data.get("collection_type", "stream")

        sources = self._build_sources()

        processor = {}
        pa = self._form_data.get("processor_agent", "").strip()
        pf = self._form_data.get("processor_function", "").strip()
        if pa and pf:
            processor["agent"] = pa
            processor["function"] = pf
            ps = self._form_data.get("processor_session", "").strip()
            if ps:
                processor["session"] = ps

        on_removed = {}
        oa = self._form_data.get("on_removed_agent", "").strip()
        of_ = self._form_data.get("on_removed_function", "").strip()
        if oa and of_:
            on_removed["agent"] = oa
            on_removed["function"] = of_
            os_ = self._form_data.get("on_removed_session", "").strip()
            if os_:
                on_removed["session"] = os_

        try:
            retro = int(self._form_data.get("retroactive_on_source_change", "0"))
            max_rep = int(self._form_data.get("max_reprocess", "0"))
        except ValueError:
            self._form_error = "Reprocess settings must be integers."
            self.update()
            return

        try:
            DataCollection.objects.create(
                name=name,
                description=self._form_data.get("description", "").strip(),
                collection_type=collection_type,
                sources=sources,
                processor=processor,
                on_removed=on_removed,
                member_field=self._form_data.get("member_field", "").strip(),
                score_field=self._form_data.get("score_field", "").strip(),
                retroactive_on_source_change=retro,
                max_reprocess=max_rep,
            )
        except Exception as e:
            self._form_error = f"Failed to create: {e}"
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
