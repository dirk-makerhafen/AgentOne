"""Pipe detail view — show pipe info, consumers, and recent items."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.models.pipe import NamedPipe, NamedPipeSubscription
from server.models.tasks.task_definition_version import TaskDefinitionVersion as TDV
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.main_view import MainView


class PipeDetailView(ModelView):
    DOM_ELEMENT_CLASS = "main-view"

    TEMPLATE_STR = '''
        <div class="main-view-header">
            <div class="main-view-title">{{ pyview.subject.name }}</div>
            <div class="main-view-actions">
                <button class="panel-head-btn" title="New consumer" onclick="pyview.openCreateSubscription()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                </button>
                {% if not pyview._editing %}
                <button class="panel-head-btn" title="Edit pipe" onclick="pyview.startEdit()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button class="panel-head-btn" title="Delete pipe" onclick="pyview.deletePipe()" style="color:var(--danger)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
                {% endif %}
                <button class="panel-head-btn" title="Refresh" onclick="pyview.refresh()">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                </button>
            </div>
        </div>
        <div class="main-view-body">
            <div class="main-view-content">

                <div class="detail-card">
                    <div class="detail-card-title">Pipe</div>
                    {% if pyview._editing %}
                    <div class="detail-form-row">
                        <label>Name</label>
                        <input type="text" value="{{ pyview._edit_data.name }}" onchange="pyview.setEditField('name', this.value)">
                    </div>
                    <div class="detail-form-row">
                        <label>Description</label>
                        <input type="text" value="{{ pyview._edit_data.description }}" onchange="pyview.setEditField('description', this.value)">
                    </div>
                    <div style="display:flex;gap:8px;margin-top:12px">
                        <button class="panel-head-btn primary" onclick="pyview.saveEdit()" style="padding:4px 16px">Save</button>
                        <button class="panel-head-btn" onclick="pyview.cancelEdit()" style="padding:4px 16px">Cancel</button>
                    </div>
                    {% else %}
                    <div class="detail-row">
                        <div class="detail-row-label">Name</div>
                        <div class="detail-row-value"><code>{{ pyview.subject.name }}</code></div>
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
                        <div class="detail-row-label">Consumers
                        </div>
                        <div class="detail-row-value">{{ pyview.subscription_count }}</div>
                    </div>
                    {% endif %}
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Consumers
                            <button class="panel-head-btn" title="New consumer" onclick="pyview.openCreateSubscription()">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            </button>
                    </div>
                    {% if pyview.subscriptions %}
                        {% for sub in pyview.subscriptions %}
                        <div class="detail-card" style="margin:8px 0;padding:12px">
                            {% if pyview._editing_consumer == sub.pk %}
                            <div style="font-size:12px">
                                <div class="detail-form-row">
                                    <label>Name</label>
                                    <input type="text" value="{{ pyview._edit_consumer_data.name }}" onchange="pyview.setEditConsumerField({{ sub.pk }}, 'name', this.value)">
                                </div>
                                <div class="detail-form-row">
                                    <label>Agent</label>
                                    <select onchange="pyview.setEditConsumerField({{ sub.pk }}, 'agent', this.value)">
                                        <option value="">-- None --</option>
                                        {% for agent in pyview._all_agents %}
                                        <option value="{{ agent.pk }}"{% if pyview._edit_consumer_data.agent == agent.pk|string() %} selected{% endif %}>{{ agent.name }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                <div class="detail-form-row">
                                    <label>Session</label>
                                    <div style="display:flex;gap:8px;flex-wrap:wrap">
                                        <label style="font-weight:normal;display:flex;align-items:center;gap:4px">
                                            <input type="radio" name="ecSess_{{ sub.pk }}" value="new" onchange="pyview.setEditConsumerField({{ sub.pk }}, 'session_mode', this.value)" {% if pyview._edit_consumer_data.session_mode == 'new' %}checked{% endif %}>
                                            New each run
                                        </label>
                                        <label style="font-weight:normal;display:flex;align-items:center;gap:4px">
                                            <input type="radio" name="ecSess_{{ sub.pk }}" value="existing" onchange="pyview.setEditConsumerField({{ sub.pk }}, 'session_mode', this.value)" {% if pyview._edit_consumer_data.session_mode == 'existing' %}checked{% endif %}>
                                            Reuse
                                        </label>
                                    </div>
                                    {% if pyview._edit_consumer_data.session_mode == 'existing' %}
                                    <input type="text" value="{{ pyview._edit_consumer_data.session_name }}" onchange="pyview.setEditConsumerField({{ sub.pk }}, 'session_name', this.value)" placeholder="Session name" style="margin-top:4px">
                                    {% endif %}
                                </div>
                                <div class="detail-form-row">
                                    <label>Active</label>
                                    <label style="font-weight:normal">
                                        <input type="checkbox" onchange="pyview.setEditConsumerField({{ sub.pk }}, 'is_active', this.checked ? 'true' : 'false')" {% if pyview._edit_consumer_data.is_active == 'true' %}checked{% endif %}>
                                        Enable consumer
                                    </label>
                                </div>
                                <div class="detail-form-row">
                                    <label>Args template</label>
                                    <textarea rows="2" onchange="pyview.setEditConsumerField({{ sub.pk }}, 'arguments_template', this.value)" style="font-family:monospace;font-size:12px;width:100%;box-sizing:border-box" placeholder='{"extra_param": "value"}'>{{ pyview._edit_consumer_data.arguments_template }}</textarea>
                                </div>
                                <div style="display:flex;gap:8px;margin-top:8px">
                                    <button class="panel-head-btn primary" onclick="pyview.saveEditConsumer({{ sub.pk }})" style="padding:4px 16px">Save</button>
                                    <button class="panel-head-btn" onclick="pyview.cancelEditConsumer()" style="padding:4px 16px">Cancel</button>
                                </div>
                            </div>
                            {% else %}
                            <div style="display:flex;justify-content:space-between;align-items:center">
                                <div>
                                    <strong>{{ sub.name or sub.pipe.name }}</strong>
                                    <span style="margin-left:8px;font-size:12px;color:var(--muted)">
                                        &rarr; {{ sub.consumer_task }}
                                    </span>
                                </div>
                                <div style="display:flex;gap:8px;align-items:center">
                                    <span class="detail-badge {% if sub.is_active %}ok{% else %}warn{% endif %}"
                                          style="cursor:pointer" onclick="pyview.toggleSubscription({{ sub.pk }})">
                                        {% if sub.is_active %}active{% else %}paused{% endif %}
                                    </span>
                                    <button class="panel-head-btn" title="Edit" onclick="pyview.startEditConsumer({{ sub.pk }})">
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                                    </button>
                                    <button class="panel-head-btn" title="Delete" onclick="pyview.deleteSubscription({{ sub.pk }})">
                                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                                    </button>
                                </div>
                            </div>
                            <div style="margin-top:6px;font-size:12px;color:var(--muted);display:flex;gap:12px;flex-wrap:wrap">
                                {% if sub.agent %}
                                <span><strong>Agent:</strong> {{ sub.agent }}</span>
                                {% endif %}
                                <span><strong>Session:</strong> {% if sub.session_mode == 'new' %}new each run{% else %}{{ sub.session_name or 'auto' }}{% endif %}</span>
                                {% if sub.arguments_template %}
                                <span><strong>Args:</strong> <code>{{ sub.arguments_template }}</code></span>
                                {% endif %}
                            </div>
                            {% endif %}
                        </div>
                        {% endfor %}
                    {% else %}
                        <div style="padding:12px;color:var(--muted);text-align:center">
                            No consumers yet.
                            <button class="panel-head-btn" onclick="pyview.openCreateSubscription()">Create one</button>
                        </div>
                    {% endif %}
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Registered producers</div>
                    {% if pyview.registered_producers %}
                        {% for tdv in pyview.registered_producers %}
                        <div class="detail-row" style="border-bottom:1px solid var(--border)">
                            <div class="detail-row-label">{{ tdv.task_definition.name if tdv.task_definition else tdv.pk }}</div>
                            <div class="detail-row-value" style="font-size:12px">
                                <code>{{ tdv.description[:60] if tdv.description else '' }}</code>
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div style="padding:12px;color:var(--muted);text-align:center">
                            No task definitions registered as producers.
                        </div>
                    {% endif %}
                    <div class="detail-form-hint" style="padding:4px 0 0 0">
                        Task definitions that list this pipe name in their <code>pipe_output_names</code>.
                    </div>
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Recent items</div>
                    <div style="display:flex;gap:4px;margin:8px 0;font-size:11px;flex-wrap:wrap">
                        <button class="panel-head-btn {% if not pyview._item_status_filter %}primary{% endif %}" onclick="pyview.setItemFilter('')" style="padding:2px 10px;font-size:11px">All</button>
                        <button class="panel-head-btn {% if pyview._item_status_filter == 'ENDED' %}primary{% endif %}" onclick="pyview.setItemFilter('ENDED')" style="padding:2px 10px;font-size:11px">Ended</button>
                        <button class="panel-head-btn {% if pyview._item_status_filter == 'ACTIVE' %}primary{% endif %}" onclick="pyview.setItemFilter('ACTIVE')" style="padding:2px 10px;font-size:11px">Active</button>
                        <button class="panel-head-btn {% if pyview._item_status_filter == 'WAITING' %}primary{% endif %}" onclick="pyview.setItemFilter('WAITING')" style="padding:2px 10px;font-size:11px">Waiting</button>
                        <button class="panel-head-btn {% if pyview._item_status_filter == 'NEW' %}primary{% endif %}" onclick="pyview.setItemFilter('NEW')" style="padding:2px 10px;font-size:11px">New</button>
                    </div>
                    {% if pyview.recent_items %}
                        {% for item in pyview.recent_items %}
                        <div class="detail-row" style="border-bottom:1px solid var(--border);padding:6px 0">
                            <div style="display:flex;justify-content:space-between;align-items:center">
                                <span style="font-weight:600;font-size:12px">#{{ item.pk }}</span>
                                <span class="detail-badge {% if item.status == 'ENDED' %}ok{% elif item.status == 'ACTIVE' %}warn{% else %}info{% endif %}">{{ item.status }}</span>
                            </div>
                            <div style="font-family:monospace;font-size:12px;margin-top:2px;color:var(--muted)">
                                {{ item.carguments_json|truncate(80) }}
                            </div>
                            <div style="font-size:11px;color:var(--muted);margin-top:2px">
                                {{ item.created_at }} &mdash; {{ item.task_definition.name if item.task_definition else '?' }}
                            </div>
                        </div>
                        {% endfor %}
                    {% else %}
                        <div style="padding:12px;color:var(--muted);text-align:center">
                            No items published yet.
                        </div>
                    {% endif %}
                </div>

            </div>
        </div>
    '''

    def __init__(self, subject: NamedPipe, parent, **kwargs):
        super().__init__(subject, parent, **kwargs)
        self._editing = False
        self._edit_data: dict[str, str] = {
            "name": subject.name,
            "description": subject.description,
        }
        self._editing_consumer: int | None = None
        self._edit_consumer_data: dict[str, str] = {}
        self._item_status_filter: str = ""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def subscriptions(self) -> list[NamedPipeSubscription]:
        return list(self.subject.subscriptions.select_related("consumer_task", "agent").all())

    @property
    def subscription_count(self) -> int:
        return self.subject.subscriptions.count()

    @property
    def _all_agents(self) -> list:
        from server.models.agents.agent import AgentModel
        return list(AgentModel.objects.all().order_by("name"))

    @property
    def registered_producers(self) -> list[TDV]:
        return list(
            TDV.objects.filter(
                pipe_output_names__contains=self.subject.name,
            ).order_by("pk")[:20]
        )

    @property
    def recent_items(self) -> list:
        from server.models.tasks.agent_task_call import AgentTaskCall
        qs = AgentTaskCall.objects.filter(
            pipe_output_names__contains=self.subject.name,
        ).select_related("task_definition")
        if self._item_status_filter:
            qs = qs.filter(status=self._item_status_filter)
        return list(qs.order_by("-pk")[:20])

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def toggleSubscription(self, pk: int) -> None:
        try:
            sub = NamedPipeSubscription.objects.get(pk=pk)
            sub.is_active = not sub.is_active
            sub.save(update_fields=["is_active"])
            self.update()
        except NamedPipeSubscription.DoesNotExist:
            pass

    def deleteSubscription(self, pk: int) -> None:
        NamedPipeSubscription.objects.filter(pk=pk).delete()
        self.update()

    def startEditConsumer(self, pk: int) -> None:
        import json as _json
        try:
            sub = NamedPipeSubscription.objects.select_related(
                "consumer_task", "agent"
            ).get(pk=pk)
        except NamedPipeSubscription.DoesNotExist:
            return
        self._editing_consumer = pk
        self._edit_consumer_data = {
            "name": sub.name or "",
            "agent": str(sub.agent_id or ""),
            "session_mode": sub.session_mode,
            "session_name": sub.session_name or "",
            "is_active": "true" if sub.is_active else "false",
            "arguments_template": (
                _json.dumps(sub.arguments_template, indent=2)
                if sub.arguments_template else "{}"
            ),
        }
        self.update()

    def cancelEditConsumer(self) -> None:
        self._editing_consumer = None
        self._edit_consumer_data = {}
        self.update()

    def setEditConsumerField(self, pk: int, field: str, value: str) -> None:
        self._edit_consumer_data[field] = value
        self.update()

    def saveEditConsumer(self, pk: int) -> None:
        import json as _json
        d = self._edit_consumer_data
        try:
            sub = NamedPipeSubscription.objects.get(pk=pk)
        except NamedPipeSubscription.DoesNotExist:
            return

        sub.name = d.get("name", "")
        agent_pk = d.get("agent", "").strip()
        if agent_pk:
            from server.models.agents.agent import AgentModel
            try:
                sub.agent = AgentModel.objects.get(pk=agent_pk)
            except AgentModel.DoesNotExist:
                sub.agent = None
        else:
            sub.agent = None
        sub.session_mode = d.get("session_mode", "new")
        sub.session_name = d.get("session_name", "").strip()
        sub.is_active = d.get("is_active") == "true"
        raw_args = d.get("arguments_template", "{}").strip()
        if raw_args:
            try:
                parsed = _json.loads(raw_args)
                if isinstance(parsed, dict):
                    sub.arguments_template = parsed
            except _json.JSONDecodeError:
                pass
        sub.save()
        self._editing_consumer = None
        self._edit_consumer_data = {}
        self.update()

    def setItemFilter(self, status: str) -> None:
        self._item_status_filter = status
        self.update()

    def openCreateSubscription(self) -> None:
        from ui.main.pipe.create import PipeSubscriptionCreateView
        PipeSubscriptionCreateView.prefill_pipe_pk = self.subject.pk
        for klass in (PipeSubscriptionCreateView,):
            parent = self._find_main_view()
            if parent:
                parent.create_and_open_tab(klass, parent.subject)

    def startEdit(self) -> None:
        self._editing = True
        self._edit_data = {
            "name": self.subject.name,
            "description": self.subject.description,
        }
        self.update()

    def cancelEdit(self) -> None:
        self._editing = False
        self.update()

    def setEditField(self, field: str, value: str) -> None:
        self._edit_data[field] = value
        self.update()

    def saveEdit(self) -> None:
        name = self._edit_data.get("name", "").strip()
        if not name:
            return
        self.subject.name = name
        self.subject.description = self._edit_data.get("description", "").strip()
        self.subject.save(update_fields=["name", "description"])
        self._editing = False
        self.update()

    def deletePipe(self) -> None:
        self.subject.delete()
        self._close_tab()

    def refresh(self) -> None:
        self.update()

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _find_main_view(self):
        parent = self.parent
        while parent and not hasattr(parent, "create_and_open_tab"):
            parent = parent.parent
        return parent
