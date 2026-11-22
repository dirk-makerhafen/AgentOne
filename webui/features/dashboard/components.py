"""Dashboard components (the live activity overview)."""

from __future__ import annotations

from django.http import Http404

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
            # Rows are inlined so an SSE reset does not fan out N placeholder loads.
            "inline_children": True,
        },
        data.keys,
    )


def _build_dashboard_activity_row(request, pk, params):
    from webui.features.dashboard.activity import build_activity_row

    item, keys = build_activity_row(pk, params.get("kind", "query"))
    if item is None:
        raise Http404(f"unknown activity row {pk}")
    return ComponentData({"item": item}, keys, reset=False)


def register_dashboard_components():
    register(
        ComponentSpec(
            "dashboard-activity",
            "dashboard/parts/activity.html",
            _build_dashboard_activity,
        )
    )
    register(
        ComponentSpec(
            "dashboard-activity-row",
            "dashboard/parts/activity_row.html",
            _build_dashboard_activity_row,
        )
    )
