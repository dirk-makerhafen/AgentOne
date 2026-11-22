"""Dashboard components (the live activity overview)."""

from __future__ import annotations

from webui.core.components import ComponentData, ComponentSpec, register


def _build_dashboard_activity(request, pk, params):
    from webui.features.dashboard.activity import build_activity

    data = build_activity()
    return ComponentData(
        {
            "items": data.items,
            "active_count": data.active_count,
            "waiting_count": data.waiting_count,
            "approval_count": data.approval_count,
        },
        data.keys,
    )


def register_dashboard_components():
    register(
        ComponentSpec(
            "dashboard-activity",
            "dashboard/parts/activity.html",
            _build_dashboard_activity,
        )
    )
