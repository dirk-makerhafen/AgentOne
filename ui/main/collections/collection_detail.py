"""Detail view for a DataCollection (stream or ordered set)."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from server.models.agents.agent import AgentModel
from server.models.collections import DataCollection, CollectionItem
from runtime.agents.agent import Agent
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class CollectionDetailView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">{{ pyview.subject.name }}</div>
            <div class="main-view-actions">
                {% if not pyview._editing %}
                <button class="panel-head-btn" title="Reprocess" onclick="pyview.reprocess()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" width="18" height="18"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
                <button class="panel-head-btn" title="Edit" onclick="pyview.startEdit()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" width="18" height="18"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button class="panel-head-btn" title="Delete" onclick="pyview.deleteCollection()" style="color:var(--danger)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" width="18" height="18"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
                {% endif %}
                <button class="panel-head-btn" title="Refresh" onclick="pyview.refresh()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" width="18" height="18"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content">

                {# --- Basic info card --- #}
                <div class="detail-card">
                    <div class="detail-card-title">Data collection</div>
                    {% if pyview._editing %}
                    <div class="detail-form-row">
                        <label>Name</label>
                        <input type="text" value="{{ pyview._edit_data.name }}" onchange="pyview.setEditField('name', this.value)">
                    </div>
                    <div class="detail-form-row">
                        <label>Description</label>
                        <input type="text" value="{{ pyview._edit_data.description }}" onchange="pyview.setEditField('description', this.value)">
                    </div>
                    <div class="detail-form-row">
                        <label>Type</label>
                        <select onchange="pyview.onEditTypeChange(this.value)">
                            <option value="stream"{% if pyview._edit_data.collection_type == 'stream' %} selected{% endif %}>Stream (append-only)</option>
                            <option value="set"{% if pyview._edit_data.collection_type == 'set' %} selected{% endif %}>Ordered Set (mutable)</option>
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label>Active</label>
                        <label style="font-weight:normal">
                            <input type="checkbox" onchange="pyview.setEditField('is_active', this.checked ? 'true' : 'false')" {% if pyview._edit_data.is_active == 'true' %}checked{% endif %}>
                            Enable data flow
                        </label>
                    </div>
                    {% else %}
                    <div class="detail-row">
                        <div class="detail-row-label">Name</div>
                        <div class="detail-row-value"><code>{{ pyview.subject.name }}</code></div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Type</div>
                        <div class="detail-row-value">
                            <span class="detail-badge {% if pyview.subject.collection_type == 'stream' %}ok{% else %}info{% endif %}">
                                {{ pyview.subject.get_collection_type_display() }}
                            </span>
                        </div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Active</div>
                        <div class="detail-row-value">
                            <span class="detail-badge {% if pyview.subject.is_active %}ok{% else %}warn{% endif %}">
                                {% if pyview.subject.is_active %}active{% else %}paused{% endif %}
                            </span>
                        </div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Description</div>
                        <div class="detail-row-value">
                            {% if pyview.subject.description %}
                                {{ pyview.subject.description }}
                            {% else %}
                                <span style="color:var(--muted)">&mdash;</span>
                            {% endif %}
                        </div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Items</div>
                        <div class="detail-row-value">{{ pyview.item_count }}</div>
                    </div>
                    {% endif %}
                </div>

                {# --- Sources card --- #}
                <div class="detail-card">
                    <div class="detail-card-title">
                        Sources
                        {% if pyview._editing %}
                        <button class="panel-head-btn" onclick="pyview.addSource()" title="Add source" style="font-size:11px;padding:2px 8px;margin-left:8px">+ Add</button>
                        {% endif %}
                    </div>
                    {% if pyview._editing %}
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
                                    <div style="display:flex;gap:4px">
                                        <select onchange="pyview.addSourceValue('{{ src.uid }}','agent_values',this.value);this.value=''" style="font-size:11px;padding:2px 4px">
                                            <option value="">+ Add agent</option>
                                            {% for a in pyview.agent_list %}
                                            <option value="{{ a.name }}"{% if a.name in src.agent_values %} disabled{% endif %}>{{ a.name }}</option>
                                            {% endfor %}
                                        </select>
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
                                    <div style="display:flex;gap:4px">
                                        <select onchange="pyview.addSourceValue('{{ src.uid }}','function_values',this.value);this.value=''" style="font-size:11px;padding:2px 4px">
                                            <option value="">+ Add function</option>
                                            {% for f in pyview.all_function_names %}
                                            <option value="{{ f }}"{% if f in src.function_values %} disabled{% endif %}>{{ f }}</option>
                                            {% endfor %}
                                        </select>
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
                                    <div style="display:flex;gap:4px">
                                        <select onchange="pyview.addSourceValue('{{ src.uid }}','session_values',this.value);this.value=''" style="font-size:11px;padding:2px 4px">
                                            <option value="">+ Add session</option>
                                            <option value="default">default</option>
                                            {% for s in pyview.session_names_list %}
                                            <option value="{{ s }}"{% if s in src.session_values %} disabled{% endif %}>{{ s }}</option>
                                            {% endfor %}
                                        </select>
                                        <div class="detail-form-hint" style="margin-top:1px">Leave empty to match any session.</div>
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
                    {% else %}
                    <div style="padding:8px;font-family:monospace;font-size:12px;white-space:pre-wrap;max-height:200px;overflow:auto">
                        {{ pyview.sources_json }}
                    </div>
                    {% endif %}
                </div>

                {# --- Processor card --- #}
                <div class="detail-card">
                    <div class="detail-card-title">Processor</div>
                    {% if pyview._editing %}
                    <div class="detail-form-row">
                        <label>Agent</label>
                        <select onchange="pyview.onEditProcessorAgentChange(this.value)">
                            <option value="">-- Select agent --</option>
                            {% for agent in pyview.agent_list %}
                            <option value="{{ agent.name }}"{% if pyview._edit_data.processor_agent == agent.name %} selected{% endif %}>{{ agent.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label>Function</label>
                        <select onchange="pyview.setEditField('processor_function', this.value)">
                            <option value="">-- Select function --</option>
                            {% for tname in pyview.edit_processor_functions %}
                            <option value="{{ tname }}"{% if pyview._edit_data.processor_function == tname %} selected{% endif %}>{{ tname }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label>Session</label>
                        <input type="text" value="{{ pyview._edit_data.processor_session }}" onchange="pyview.setEditField('processor_session', this.value)" placeholder="default (or {source_agent.name} template)">
                    </div>
                    {% elif pyview.subject.processor %}
                    <div class="detail-row">
                        <div class="detail-row-label">Agent</div>
                        <div class="detail-row-value">{{ pyview.subject.processor.get('agent', '?') }}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Function</div>
                        <div class="detail-row-value"><code>{{ pyview.subject.processor.get('function', '?') }}</code></div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Session</div>
                        <div class="detail-row-value">{{ pyview.subject.processor.get('session', 'auto') }}</div>
                    </div>
                    {% else %}
                    <div style="padding:12px;color:var(--muted);text-align:center">
                        No processor configured.
                    </div>
                    {% endif %}
                </div>

                {# --- Set configuration (sets only) --- #}
                {% if pyview.show_set_config %}
                <div class="detail-card">
                    <div class="detail-card-title">Set configuration</div>
                    {% if pyview._editing %}
                    <div class="detail-form-row">
                        <label>Member field</label>
                        <input type="text" value="{{ pyview._edit_data.member_field }}" onchange="pyview.setEditField('member_field', this.value)" placeholder="item.get('session', 'unknown')">
                    </div>
                    <div class="detail-form-row">
                        <label>Score field</label>
                        <input type="text" value="{{ pyview._edit_data.score_field }}" onchange="pyview.setEditField('score_field', this.value)" placeholder="float(item.get('timestamp', 0))">
                    </div>
                    <div style="margin-top:8px">
                        <div class="detail-card-title">On removed handler</div>
                    </div>
                    <div class="detail-form-row">
                        <label>Agent</label>
                        <select onchange="pyview.onEditRemovedAgentChange(this.value)">
                            <option value="">-- Select agent --</option>
                            {% for agent in pyview.agent_list %}
                            <option value="{{ agent.name }}"{% if pyview._edit_data.on_removed_agent == agent.name %} selected{% endif %}>{{ agent.name }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label>Function</label>
                        <select onchange="pyview.setEditField('on_removed_function', this.value)">
                            <option value="">-- Select function --</option>
                            {% for tname in pyview.edit_on_removed_functions %}
                            <option value="{{ tname }}"{% if pyview._edit_data.on_removed_function == tname %} selected{% endif %}>{{ tname }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="detail-form-row">
                        <label>Session</label>
                        <input type="text" value="{{ pyview._edit_data.on_removed_session }}" onchange="pyview.setEditField('on_removed_session', this.value)" placeholder="default">
                    </div>
                    {% else %}
                    <div class="detail-row">
                        <div class="detail-row-label">Member field</div>
                        <div class="detail-row-value"><code>{{ pyview.subject.member_field or 'auto (hash)' }}</code></div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Score field</div>
                        <div class="detail-row-value"><code>{{ pyview.subject.score_field or 'timestamp' }}</code></div>
                    </div>
                    {% if pyview.subject.on_removed %}
                    <div class="detail-row">
                        <div class="detail-row-label">On removed</div>
                        <div class="detail-row-value">
                            {{ pyview.subject.on_removed.get('agent', '?') }} &rarr;
                            <code>{{ pyview.subject.on_removed.get('function', '?') }}</code>
                        </div>
                    </div>
                    {% endif %}
                    {% endif %}
                </div>
                {% endif %}

                {# --- Reprocess settings card --- #}
                <div class="detail-card">
                    <div class="detail-card-title">Reprocess settings</div>
                    {% if pyview._editing %}
                    <div class="detail-form-row">
                        <label>Retroactive on source change</label>
                        <input type="number" value="{{ pyview._edit_data.retroactive_on_source_change }}" onchange="pyview.setEditField('retroactive_on_source_change', this.value)" placeholder="0 = off" style="width:100px">
                    </div>
                    <div class="detail-form-row">
                        <label>Max reprocess</label>
                        <input type="number" value="{{ pyview._edit_data.max_reprocess }}" onchange="pyview.setEditField('max_reprocess', this.value)" placeholder="0 = off" style="width:100px">
                    </div>
                    {% else %}
                    <div class="detail-row">
                        <div class="detail-row-label">Retroactive on source change</div>
                        <div class="detail-row-value">{{ pyview.subject.retroactive_on_source_change or 0 }}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-row-label">Max reprocess</div>
                        <div class="detail-row-value">{{ pyview.subject.max_reprocess or 0 }}</div>
                    </div>
                    {% endif %}
                </div>

                {# --- Derived flows --- #}
                <div class="detail-card">
                    <div class="detail-card-title">
                        Derived flows
                        <span style="font-size:11px;font-weight:normal;color:var(--muted)">(collections sourcing from this one)</span>
                    </div>
                    {% if pyview.derived_flows %}
                        {% for flow in pyview.derived_flows %}
                        <div class="detail-row" style="border-bottom:1px solid var(--border)">
                            <div class="detail-row-label">
                                <span class="detail-badge {% if flow.collection_type == 'stream' %}ok{% else %}info{% endif %}" style="font-size:10px;margin-right:4px">
                                    {{ flow.get_collection_type_display() }}
                                </span>
                                {{ flow.name }}
                            </div>
                            <div class="detail-row-value" style="font-size:12px">
                                {% if flow.is_active %}
                                <span style="color:var(--success)">active</span>
                                {% else %}
                                <span style="color:var(--muted)">paused</span>
                                {% endif %}
                                &middot; {{ flow.items.count() }} items
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div style="padding:12px;color:var(--muted);text-align:center">
                            No derived flows.
                        </div>
                    {% endif %}
                </div>

                {# --- Save/Cancel buttons (edit mode) --- #}
                {% if pyview._editing %}
                <div style="display:flex;gap:8px;margin-top:12px">
                    <button class="panel-head-btn primary" onclick="pyview.saveEdit()" style="padding:4px 16px">Save</button>
                    <button class="panel-head-btn" onclick="pyview.cancelEdit()" style="padding:4px 16px">Cancel</button>
                </div>
                {% endif %}

                {# --- Recent items --- #}
                <div class="detail-card">
                    <div class="detail-card-title">Recent items</div>
                    {% if pyview.recent_items %}
                        {% for item in pyview.recent_items %}
                        <div class="detail-row" style="border-bottom:1px solid var(--border);padding:6px 0">
                            <div style="display:flex;justify-content:space-between;align-items:center">
                                <span style="font-weight:600;font-size:12px;font-family:monospace">{{ item.member }}</span>
                                <span style="font-size:11px;color:var(--muted)">score={{ item.score }}</span>
                            </div>
                            <div style="font-family:monospace;font-size:11px;margin-top:2px;color:var(--muted);max-height:60px;overflow:hidden">
                                {{ item.value|truncate(80) }}
                            </div>
                            <div style="font-size:11px;color:var(--muted);margin-top:2px">
                                {{ item.created_at }}
                                {% if item.source_call %}
                                &mdash; call #{{ item.source_call.pk }}
                                {% endif %}
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div style="padding:12px;color:var(--muted);text-align:center">
                            No items yet.
                        </div>
                    {% endif %}
                </div>

            </div>
        </div>
    '''

    def __init__(self, subject: DataCollection, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._editing = False
        self._edit_data: dict[str, str] = self._snapshot()
        self._source_uid_counter = 0
        self._source_entries: list[dict] = self._init_sources_from_subject()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def item_count(self) -> int:
        return self.subject.items.count()

    @property
    def sources_json(self) -> str:
        return json.dumps(self.subject.sources, indent=2) if self.subject.sources else "[]"

    @property
    def derived_flows(self) -> list[DataCollection]:
        from server.models.collections import DataCollection
        name = self.subject.name
        results: list[DataCollection] = []
        for dc in DataCollection.objects.filter(is_active=True).exclude(pk=self.subject.pk):
            for src in (dc.sources or []):
                if src.get("type") in ("stream", "set") and src.get(src.get("type", "")) == name:
                    results.append(dc)
                    break
        return results

    @property
    def recent_items(self):
        return list(
            CollectionItem.objects.filter(collection=self.subject)
            .select_related("source_call")
            .order_by("-pk")[:20]
        )

    @property
    def agent_list(self):
        return list(AgentModel.objects.all().order_by("name"))

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

    @property
    def edit_processor_functions(self):
        name = self._edit_data.get("processor_agent", "")
        if not name:
            return []
        agent_model = AgentModel.objects.filter(name=name).first()
        if not agent_model:
            return []
        agent = Agent(agent_model=agent_model)
        return sorted(set(tdv.task_definition.name for tdv in agent.allowedTasks))

    @property
    def show_set_config(self) -> bool:
        if self._editing:
            return self._edit_data.get("collection_type") == "set"
        return self.subject.collection_type == "set"

    @property
    def edit_on_removed_functions(self):
        name = self._edit_data.get("on_removed_agent", "")
        if not name:
            return []
        agent_model = AgentModel.objects.filter(name=name).first()
        if not agent_model:
            return []
        agent = Agent(agent_model=agent_model)
        return sorted(set(tdv.task_definition.name for tdv in agent.allowedTasks))

    # ------------------------------------------------------------------
    # Source entries (edit mode)
    # ------------------------------------------------------------------

    @property
    def all_function_names(self):
        names = set()
        for agent_model in AgentModel.objects.all():
            agent = Agent(agent_model=agent_model)
            for tdv in agent.allowedTasks:
                names.add(tdv.task_definition.name)
            for tdv in agent.allowedTools:
                names.add(tdv.task_definition.name)
            for tdv in agent.allowedCommands:
                names.add(tdv.task_definition.name)
        return sorted(names)

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

    def _init_sources_from_subject(self) -> list[dict]:
        entries = []
        for src in self.subject.sources or []:
            uid = f"src_{self._source_uid_counter}"
            self._source_uid_counter += 1
            t = src.get("type", "query")
            entry: dict = {"uid": uid, "type": t}
            if t == "query":
                entry["project"] = src.get("project", "")
                agent = src.get("agent", "")
                entry["agent_values"] = agent if isinstance(agent, list) else ([agent] if agent else [])
                function = src.get("function", "")
                entry["function_values"] = function if isinstance(function, list) else ([function] if function else [])
                session = src.get("session", "")
                entry["session_values"] = session if isinstance(session, list) else ([session] if session else [])
            elif t == "stream":
                entry["stream"] = src.get("stream", "")
            elif t == "set":
                entry["set"] = src.get("set", "")
            entries.append(entry)
        return entries

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

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def reprocess(self) -> None:
        from server.tasks import reprocess_collection
        reprocess_collection.delay(self.subject.name)

    def startEdit(self) -> None:
        self._editing = True
        self._edit_data = self._snapshot()
        self._source_uid_counter = 0
        self._source_entries = self._init_sources_from_subject()
        self.update()

    def cancelEdit(self) -> None:
        self._editing = False
        self._source_entries = self._init_sources_from_subject()
        self.update()

    def setEditField(self, field: str, value: str) -> None:
        self._edit_data[field] = value
        self.update()

    def onEditTypeChange(self, value: str) -> None:
        self._edit_data["collection_type"] = value
        self.update()

    def onEditProcessorAgentChange(self, agent_name: str) -> None:
        self._edit_data["processor_agent"] = agent_name
        self._edit_data["processor_function"] = ""
        self.update()

    def onEditRemovedAgentChange(self, agent_name: str) -> None:
        self._edit_data["on_removed_agent"] = agent_name
        self._edit_data["on_removed_function"] = ""
        self.update()

    def saveEdit(self) -> None:
        d = self._edit_data
        name = d.get("name", "").strip()
        if not name:
            return
        self.subject.name = name
        self.subject.description = d.get("description", "").strip()
        self.subject.collection_type = d.get("collection_type", "stream")
        self.subject.is_active = d.get("is_active") == "true"
        self.subject.sources = self._build_sources()

        processor = {}
        pa = d.get("processor_agent", "").strip()
        pf = d.get("processor_function", "").strip()
        if pa and pf:
            processor["agent"] = pa
            processor["function"] = pf
            ps = d.get("processor_session", "").strip()
            if ps:
                processor["session"] = ps
        self.subject.processor = processor

        self.subject.member_field = d.get("member_field", "").strip()
        self.subject.score_field = d.get("score_field", "").strip()

        on_removed = {}
        oa = d.get("on_removed_agent", "").strip()
        of_ = d.get("on_removed_function", "").strip()
        if oa and of_:
            on_removed["agent"] = oa
            on_removed["function"] = of_
            os_ = d.get("on_removed_session", "").strip()
            if os_:
                on_removed["session"] = os_
        self.subject.on_removed = on_removed

        try:
            self.subject.retroactive_on_source_change = int(d.get("retroactive_on_source_change", "0"))
            self.subject.max_reprocess = int(d.get("max_reprocess", "0"))
        except ValueError:
            pass

        self.subject.save()
        self._editing = False
        self.update()

    def deleteCollection(self) -> None:
        self.subject.delete()
        self._close_tab()

    def refresh(self) -> None:
        self.subject.refresh_from_db()
        self._edit_data = self._snapshot()
        self._source_entries = self._init_sources_from_subject()
        self.update()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _snapshot(self) -> dict[str, str]:
        p = self.subject.processor or {}
        o = self.subject.on_removed or {}
        return {
            "name": self.subject.name,
            "description": self.subject.description or "",
            "collection_type": self.subject.collection_type,
            "is_active": "true" if self.subject.is_active else "false",
            "processor_agent": p.get("agent", ""),
            "processor_function": p.get("function", ""),
            "processor_session": p.get("session", ""),
            "member_field": self.subject.member_field or "",
            "score_field": self.subject.score_field or "",
            "on_removed_agent": o.get("agent", ""),
            "on_removed_function": o.get("function", ""),
            "on_removed_session": o.get("session", ""),
            "retroactive_on_source_change": str(self.subject.retroactive_on_source_change or 0),
            "max_reprocess": str(self.subject.max_reprocess or 0),
        }

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent

    def _close_tab(self) -> None:
        parent = self._find_main_view()
        if parent and hasattr(parent, "close_tab"):
            parent.close_tab(self)
