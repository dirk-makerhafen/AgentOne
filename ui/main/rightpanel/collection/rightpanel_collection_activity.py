"""Right panel tabs for a DataCollection (activity + derived flows)."""
from __future__ import annotations

from typing import TYPE_CHECKING
from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from server.models.collections import DataCollection, CollectionItem
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.collection.rightpanel_collection import RightPanelCollection
    from ui.app import UiApp

class RightPanelCollectionActivity(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
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

    def __init__(self, subject: DataCollection, parent: RightPanelCollection, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def entries(self) -> list[dict]:
        c = self.subject
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

