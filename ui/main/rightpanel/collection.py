"""Right panel tabs for a DataCollection (activity + derived flows)."""
from __future__ import annotations

from typing import TYPE_CHECKING
from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from server.models.collections import DataCollection, CollectionItem
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.rightpanel import RightPanel
    from ui.app import UiApp


FLOW_ICONS = {
    "activity": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    "derived": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
}


class RightPanelCollectionActivity(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-inner"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Activity</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% if pyview.entries %}
                {% for entry in pyview.entries %}
                <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 2px;font-size:12px;border-bottom:1px solid var(--border,.05)">
                    <span style="font-family:monospace;font-size:11px">{{ entry.member }}</span>
                    <span style="color:var(--muted);font-size:11px">{{ entry.since }}</span>
                </div>
                {% endfor %}
            {% else %}
                <div style="font-size:12px;color:var(--muted);padding:8px">No recent activity.</div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def collection(self) -> DataCollection | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, DataCollection) else None

    @property
    def entries(self) -> list[dict]:
        c = self.collection
        if not c:
            return []
        now = timezone.now()
        qs = CollectionItem.objects.filter(collection=c).order_by("-pk")[:20]
        rows = []
        for item in qs:
            dt = item.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=dt_timezone.utc)
            diff = now - dt
            secs = int(diff.total_seconds())
            if secs < 5:
                since = "just now"
            elif secs < 60:
                since = f"{secs}s ago"
            elif secs < 3600:
                since = f"{secs // 60}m ago"
            elif secs < 86400:
                since = f"{secs // 3600}h ago"
            else:
                since = f"{secs // 86400}d ago"
            rows.append({"member": item.member, "since": since})
        return rows


class RightPanelCollectionDerived(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel"
    TEMPLATE_STR = '''
        <div class="panel-header"><span>Derived flows</span></div>
        <div style="flex:1;overflow-y:auto;padding:8px">
            {% if pyview.flows %}
                {% for flow in pyview.flows %}
                <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 2px;font-size:12px;border-bottom:1px solid var(--border,.05)">
                    <span style="font-weight:500">{{ flow.name }}</span>
                    <span>
                        <span class="detail-badge {% if flow.collection_type == 'stream' %}ok{% else %}info{% endif %}" style="font-size:10px">
                            {{ flow.get_collection_type_display() }}
                        </span>
                    </span>
                </div>
                {% endfor %}
            {% else %}
                <div style="font-size:12px;color:var(--muted);padding:8px">No derived flows.</div>
            {% endif %}
        </div>
    '''

    def __init__(self, subject: UiApp, parent: RightPanel, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def collection(self) -> DataCollection | None:
        subj = self.parent.current_subject
        return subj if isinstance(subj, DataCollection) else None

    @property
    def flows(self) -> list[DataCollection]:
        c = self.collection
        if not c:
            return []
        name = c.name
        results: list[DataCollection] = []
        for dc in DataCollection.objects.filter(is_active=True).exclude(pk=c.pk):
            for src in (dc.sources or []):
                if src.get("type") in ("stream", "set") and src.get(src.get("type", "")) == name:
                    results.append(dc)
                    break
        return results
