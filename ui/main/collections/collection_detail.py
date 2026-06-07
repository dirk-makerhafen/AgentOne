"""Detail view for a DataCollection (stream or ordered set)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from server.models.collections import DataCollection, CollectionItem
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
                        <select onchange="pyview.setEditField('collection_type', this.value)">
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

                <div class="detail-card">
                    <div class="detail-card-title">Sources</div>
                    <div style="padding:8px;font-family:monospace;font-size:12px;white-space:pre-wrap;max-height:200px;overflow:auto">
                        {{ pyview.sources_json }}
                    </div>
                </div>

                <div class="detail-card">
                    <div class="detail-card-title">Processor</div>
                    {% if pyview.subject.processor %}
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

                {% if pyview.subject.collection_type == 'set' %}
                <div class="detail-card">
                    <div class="detail-card-title">Set configuration</div>
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
                </div>
                {% endif %}

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

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def item_count(self) -> int:
        return self.subject.items.count()

    @property
    def sources_json(self) -> str:
        import json
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

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def reprocess(self) -> None:
        from server.tasks import reprocess_collection
        reprocess_collection.delay(self.subject.name)

    def startEdit(self) -> None:
        self._editing = True
        self._edit_data = self._snapshot()
        self.update()

    def cancelEdit(self) -> None:
        self._editing = False
        self.update()

    def setEditField(self, field: str, value: str) -> None:
        self._edit_data[field] = value
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
        self.subject.save(update_fields=["name", "description", "collection_type", "is_active"])
        self._editing = False
        self.update()

    def deleteCollection(self) -> None:
        self.subject.delete()
        self._close_tab()

    def refresh(self) -> None:
        self.update()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _snapshot(self) -> dict[str, str]:
        return {
            "name": self.subject.name,
            "description": self.subject.description or "",
            "collection_type": self.subject.collection_type,
            "is_active": "true" if self.subject.is_active else "false",
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
