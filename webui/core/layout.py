"""Core page/layout helpers for the server-rendered UI.

Feature-specific sidebar/context builders live in ``webui.features.<feature>``.
Chat/session UI helpers live in ``webui.features.chats``.
"""

from __future__ import annotations

import gzip
import logging
from datetime import datetime
from importlib import import_module

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.cache import patch_vary_headers

from runtime.settings import UserSettings, get_send_key as _get_send_key
from server.models.agents.agent import AgentModel
from server.models.sessions.session import SessionModel

log = logging.getLogger(__name__)

#: Rail navigation. ``section`` is the URL name suffix used by ``webui:urls``.
NAV_SECTIONS = (
    ("dashboard", "Dashboard"),
    ("chats", "Chats"),
    ("agents", "Agents"),
    ("projects", "Projects"),
    ("workspaces", "Spaces"),
    ("skills", "Skills"),
    ("cron", "Cron"),
    ("collections", "Data flows"),
    ("workitems", "Work items"),
    ("memory", "Memory"),
    ("insights", "Insights"),
    ("logs", "Logs"),
    ("settings", "Settings"),
)

#: Which panel template each section's sidebar renders.
SIDEBAR_TEMPLATES = {
    "dashboard": "chats/sidebar.html",
    "chats": "chats/sidebar.html",
    "agents": "agents/sidebar.html",
    "projects": "projects/sidebar.html",
    "workspaces": "workspaces/sidebar.html",
    "skills": "skills/sidebar.html",
    "cron": "cron/sidebar.html",
    "collections": "collections/sidebar.html",
    "workitems": "workitems/sidebar.html",
    "memory": "memory/sidebar.html",
    "insights": "insights/sidebar.html",
    "logs": "logs/sidebar.html",
    "settings": "settings/sidebar.html",
}

_SIDEBAR_BUILDERS = {
    "dashboard": "webui.features.chats.sidebar",
    "chats": "webui.features.chats.sidebar",
    "agents": "webui.features.agents.sidebar",
    "projects": "webui.features.projects.sidebar",
    "workspaces": "webui.features.workspaces.sidebar",
    "skills": "webui.features.skills.sidebar",
    "cron": "webui.features.cron.sidebar",
    "collections": "webui.features.collections.sidebar",
    "workitems": "webui.features.workitems.sidebar",
    "memory": "webui.features.memory.sidebar",
    "insights": "webui.features.insights.sidebar",
    "logs": "webui.features.logs.sidebar",
    "settings": "webui.features.settings.sidebar",
}


def component_sidebar_url(section: str, params: dict | None = None) -> str:
    """URL of a section sidebar component (htmx variant)."""
    from webui.core.components import component_url

    return component_url(f"{section}-sidebar", None, params or {}, htmx=True)


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

def appearance() -> dict[str, str]:
    try:
        settings_obj = UserSettings()
        return {
            "skin": settings_obj.skin or "slate",
            "theme": settings_obj.theme or "system",
            "font_size": settings_obj.font_size or "default",
        }
    except Exception:  # pylint: disable=broad-exception-caught
        return {"skin": "slate", "theme": "system", "font_size": "default"}


def send_key() -> str:
    try:
        return _get_send_key()
    except Exception:  # pylint: disable=broad-exception-caught
        return "ctrl+enter"


def panel_open_default() -> bool:
    try:
        return bool(UserSettings().workspace_panel_open)
    except Exception:  # pylint: disable=broad-exception-caught
        return False


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def default_agent() -> AgentModel | None:
    qs = AgentModel.objects.filter(
        is_archived=False,
        parent_agent__isnull=True,
        parent_skill__isnull=True,
        latest_agent_version__isnull=False,
    )
    for name in ("AgentOne", "baseagent", "general-chat", "coding"):
        agent = qs.filter(name=name).first()
        if agent is not None and agent.is_user_visible:
            return agent
    for agent in qs[:25]:
        if agent.is_user_visible:
            return agent
    return None


def unique_session_name(base: str) -> str:
    name = base
    if SessionModel.objects.filter(name=name).exists():
        stamp = datetime.now().strftime("%Y.%m.%d-%H:%M:%S")
        name = f"{base} {stamp}"
        index = 2
        while SessionModel.objects.filter(name=name).exists():
            name = f"{base} {stamp}-{index}"
            index += 1
    return name


# ---------------------------------------------------------------------------
# Shell / page context
# ---------------------------------------------------------------------------

def _sidebar_project_id(request):
    """Resolve and persist the sidebar's project filter."""
    if "project" in request.GET:
        raw = request.GET.get("project") or ""
        project_id = int(raw) if raw.isdigit() else None
        if request.session.get("sidebar_project_id") != project_id:
            request.session["sidebar_project_id"] = project_id
    else:
        project_id = request.session.get("sidebar_project_id")

    from server.models.project import Project

    if project_id is not None and not Project.objects.filter(pk=project_id).exists():
        project_id = None
        request.session["sidebar_project_id"] = None
    return project_id


def page_context(request, section: str, active_id=None) -> dict:
    """Common context for every full page: rail, sidebar and preferences."""
    context = {
        "sections": NAV_SECTIONS,
        "section": section,
        "active_id": active_id,
        "sidebar_component": f"{section}-sidebar",
    }
    context.update(appearance())
    return context


def is_htmx_request(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def is_boosted_request(request) -> bool:
    return request.headers.get("HX-Boosted") == "true"


def render_page(request, section: str, template: str, context: dict | None = None,
                active_id=None) -> HttpResponse:
    """Render a page, or just the swappable shell for boosted navigation."""
    ctx = page_context(request, section, active_id)
    htmx = is_htmx_request(request)
    ctx.update(context or {})
    ctx["layout_base"] = "layout/hx_base.html" if htmx else "layout/base.html"
    # Boosted/htmx shells emit component placeholders so children load and
    # preserve themselves; full document loads inline for a complete first paint.
    ctx["component_inline"] = not htmx
    ctx["disable_history"] = template.startswith("chats/")
    response = render(request, template, ctx)
    patch_vary_headers(response, ("HX-Request",))
    response["Cache-Control"] = "private, no-cache"
    _gzip_html(request, response)
    return response


def _gzip_html(request, response, *, minimum: int = 1024) -> None:
    body = response.content
    if len(body) < minimum:
        return
    if "gzip" not in request.headers.get("Accept-Encoding", "").lower():
        return
    patch_vary_headers(response, ("Accept-Encoding",))
    response.content = gzip.compress(body, compresslevel=6)
    response["Content-Encoding"] = "gzip"
    response["Content-Length"] = str(len(response.content))


# ---------------------------------------------------------------------------
# Sidebars
# ---------------------------------------------------------------------------

def sidebar_context(request, section: str, active_id=None) -> dict:
    """Data needed by a section sidebar panel (delegated to feature modules)."""
    from server.models.project import Project

    project_id = _sidebar_project_id(request)
    ctx: dict = {
        "section": section,
        "active_id": active_id,
        "sidebar_project_id": project_id,
        "sidebar_projects": list(Project.objects.order_by("name")),
    }
    module_path = _SIDEBAR_BUILDERS.get(section)
    if module_path:
        import_module(module_path).build_sidebar_context(request, project_id, ctx)
    return ctx
