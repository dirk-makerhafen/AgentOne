"""Sidebar fragment view (shared by every domain)."""

from __future__ import annotations

from django.shortcuts import render
from django.urls import reverse

from webui.views.common import (
    SIDEBAR_TEMPLATES,
    SIDEBAR_TRIGGERS,
    _sidebar_query,
    appearance,
    sidebar_context,
)


def sidebar_fragment(request):
    section = request.GET.get("section", "chats")
    if section not in SIDEBAR_TEMPLATES:
        section = "chats"
    raw_active = request.GET.get("active", "")
    active_id = int(raw_active) if raw_active.isdigit() else None

    context = sidebar_context(request, section, active_id)
    context.update(
        {
            "section": section,
            "sidebar_template": SIDEBAR_TEMPLATES[section],
            "sidebar_triggers": SIDEBAR_TRIGGERS.get(section, ""),
            "sidebar_qs": _sidebar_query(request, section, active_id),
            "global_sse_url": f"{reverse('webui:sse')}?scope=global",
        }
    )
    context.update(appearance())
    return render(request, "webui/shell/_sidebar.html", context)
