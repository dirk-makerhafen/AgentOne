"""Right panel tabs for a DataCollection (activity + derived flows)."""
from __future__ import annotations

from typing import TYPE_CHECKING
from datetime import datetime, timezone as dt_timezone

from server.models.collections import DataCollection
from ui.lib.model_view import ModelView

if TYPE_CHECKING:
    from ui.main.rightpanel.collection.rightpanel_collection import RightPanelCollection
    from ui.app import UiApp

class RightPanelCollectionDerived(ModelView):
    DOM_ELEMENT = "div"
    DOM_ELEMENT_CLASS = "rightpanel-tab"
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

    def __init__(self, subject: DataCollection, parent: RightPanelCollection, **kwargs):
        super().__init__(subject, parent, **kwargs)

    @property
    def flows(self) -> list[DataCollection]:
        c = self.subject
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


