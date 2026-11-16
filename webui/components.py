"""Independently cacheable htmx components.

Every visible element with a server-derived state is a component with its own
URL, its own ETag and its own observable keys.  A page shell contains
placeholders; the browser loads each placeholder once and then revalidates it
only when one of its keys fires.

Two render modes
----------------

``render=full`` (default)
    Render the component *and* its children inline.  Used for direct document
    loads and for clients without JavaScript.  The response is a real tree.

``render=htmx``
    Render the component with placeholders for its children.  Used by every
    htmx request.  A parent swap therefore never destroys a child that is
    already loaded: the child placeholder carries ``hx-preserve`` and htmx
    moves the live element into the new fragment by id.

Cache policy
------------

* Live components (they have observable keys) are ``private, no-cache`` with
  an ETag.  The client sends ``If-None-Match``; an unchanged component answers
  ``204`` so htmx skips the swap and the browser keeps focus and open
  ``<details>``.
* Immutable components (finished messages, terminal responses) are
  ``private, max-age=31536000, immutable`` and carry no SSE trigger.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlencode

from django.http import Http404, HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET

__all__ = [
    "ComponentData",
    "component_url",
    "render_component",
    "render_component_ref",
    "section_sidebar",
]


@dataclass
class ComponentData:
    """Everything one component render needs from the domain layer."""

    context: dict[str, Any]
    keys: tuple[str, ...] = ()
    immutable: bool = False


@dataclass
class ComponentSpec:
    name: str
    template: str
    build: Callable[[Any, int | None, dict[str, Any]], ComponentData]
    url_name: str | None = None
    title: str = ""


_REGISTRY: dict[str, ComponentSpec] = {}


def register(spec: ComponentSpec) -> ComponentSpec:
    _REGISTRY[spec.name] = spec
    return spec


def get_spec(name: str) -> ComponentSpec:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise Http404(f"unknown component {name}") from exc


# ---------------------------------------------------------------------------
# URLs and ids
# ---------------------------------------------------------------------------

def _clean_params(params: dict[str, Any]) -> dict[str, str]:
    return {
        key: str(value)
        for key, value in params.items()
        if value not in (None, "") and key != "render"
    }


def component_id(name: str, pk: int | None, params: dict[str, Any]) -> str:
    payload = json.dumps(
        {"k": sorted(_clean_params(params).items()), "p": pk},
        separators=(",", ":"),
    )
    digest = hashlib.sha1(payload.encode()).hexdigest()[:8]
    return f"c-{name}-{pk if pk is not None else 0}-{digest}"


def component_url(
    name: str,
    pk: int | None = None,
    params: dict[str, Any] | None = None,
    *,
    htmx: bool = True,
) -> str:
    spec = get_spec(name)
    if spec.url_name:
        base = reverse(f"webui:{spec.url_name}")
    elif pk is None:
        base = reverse("webui:component_root", args=[name])
    else:
        base = reverse("webui:component", args=[name, pk])
    query = _clean_params(params or {})
    if htmx:
        query["render"] = "htmx"
    return f"{base}?{urlencode(query)}" if query else base


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _etag(html: str) -> str:
    """Stable ETag for one rendered component.

    CSRF tokens are masked per request by Django, so two identical renders
    would otherwise never share an ETag and the client would re-render on every
    event.  Masking them is safe: the token is not part of the component state.
    """
    canonical = re.sub(
        r'(name="csrfmiddlewaretoken" value=")[^"]*(")', r"\1\2", html
    )
    return '"' + hashlib.sha256(canonical.encode()).hexdigest()[:32] + '"'


def _trigger(keys: tuple[str, ...]) -> str:
    if not keys:
        return ""
    parts = [f"sse:{key} delay:150ms" for key in keys]
    parts.append("sse:reset delay:150ms")
    return ", ".join(parts)


def _open_tag(
    name: str,
    pk: int | None,
    params: dict[str, Any],
    *,
    etag: str | None = None,
    keys: tuple[str, ...] = (),
    placeholder: bool = False,
) -> str:
    url = component_url(name, pk, params, htmx=True)
    attrs = [
        f'id="{component_id(name, pk, params)}"',
        'class="c"',
        f'data-component="{escape(name)}"',
        f'hx-get="{escape(url)}"',
        'hx-swap="outerHTML"',
        'hx-sync="this:replace"',
    ]
    if etag and not placeholder:
        attrs.append(f'data-component-etag="{escape(etag)}"')
    if placeholder:
        attrs.append('hx-trigger="load"')
        attrs.append("hx-preserve")
    else:
        trigger = _trigger(keys)
        if trigger:
            attrs.append(f'hx-trigger="{escape(trigger)}"')
    return "<div " + " ".join(attrs) + ">"


def _wrap(
    name: str,
    pk: int | None,
    params: dict[str, Any],
    inner: str,
    *,
    etag: str | None,
    keys: tuple[str, ...],
    placeholder: bool = False,
) -> str:
    if placeholder and name.endswith("-sidebar"):
        # The boosted shell is asserted to contain the sidebar landmark even
        # before the component request settles.
        inner = '<aside class="sidebar" id="sidebar"></aside>'
    return _open_tag(name, pk, params, etag=etag, keys=keys, placeholder=placeholder) + inner + "</div>"


def _collect_keys(data: ComponentData) -> tuple[str, ...]:
    return tuple(dict.fromkeys(key for key in data.keys if key))


def _render_into(
    name: str,
    pk: int | None,
    params: dict[str, Any],
    *,
    inline: bool,
    request=None,
) -> tuple[str, ComponentData]:
    spec = get_spec(name)
    data = spec.build(request, pk, params)
    context = dict(data.context)
    context["component_inline"] = inline
    html = render_to_string(spec.template, context, request=request)
    return html, data


def _render_request(request, name: str, pk: int | None, params: dict[str, Any]) -> HttpResponse:
    full = request.GET.get("render") != "htmx"
    spec = get_spec(name)
    data = spec.build(request, pk, params)
    context = dict(data.context)
    context["component_inline"] = full
    html = render_to_string(spec.template, context, request=request)
    keys = () if data.immutable else _collect_keys(data)

    response = HttpResponse()
    response["Vary"] = "Cookie"
    if data.immutable:
        response["Cache-Control"] = "private, max-age=31536000, immutable"
    else:
        response["Cache-Control"] = "private, no-cache"

    etag = _etag(html)
    response["ETag"] = etag
    if not data.immutable and request.headers.get("If-None-Match") == etag:
        response.status_code = 204
        return response

    response.content = _wrap(name, pk, params, html, etag=etag, keys=keys)
    response["Content-Length"] = str(len(response.content))
    return response


@require_GET
def render_component(request, name: str, pk: int | None = None):
    """Serve one component (``/app/c/<name>[/<pk>]``)."""
    params = {key: request.GET.get(key) for key in request.GET if key != "render"}
    return _render_request(request, name, pk, params)


@require_GET
def section_sidebar(request, section: str):
    """Serve one section's sidebar component (``/app/chats/sidebar``)."""
    name = f"{section}-sidebar"
    if name not in _REGISTRY:
        raise Http404(f"no sidebar for {section}")
    params = {key: request.GET.get(key) for key in request.GET if key != "render"}
    return _render_request(request, name, None, params)


def render_component_ref(context, name: str, pk=None, params=None) -> str:
    """Template-tag entry point: inline render or placeholder."""
    params = params or {}
    if context.get("component_inline"):
        request = context.get("request")
        html, data = _render_into(name, pk, params, inline=True, request=request)
        return mark_safe(
            _wrap(
                name,
                pk,
                params,
                html,
                etag=None,
                keys=() if data.immutable else _collect_keys(data),
            )
        )
    return mark_safe(_wrap(name, pk, params, "", etag=None, keys=(), placeholder=True))


# ---------------------------------------------------------------------------
# Small shared helpers
# ---------------------------------------------------------------------------

def _session(pk: int):
    from server.models.sessions.session import SessionModel

    return SessionModel.objects.select_related(
        "latest_session_version__agent",
        "latest_session_version__agent__latest_agent_version",
        "latest_session_version__agent__latest_agent_version__agent_settings",
        "latest_session_version__pinned_agent_version",
        "latest_session_version__session_settings",
        "latest_session_version__workspace",
        "parent_project",
    ).get(pk=pk)


def _message(pk: int):
    from django.db.models import Prefetch

    from server.models.message import Message, MessagePart

    return (
        Message.objects.select_related("response")
        .prefetch_related(
            Prefetch(
                "parts",
                queryset=MessagePart.objects.select_related(
                    "content",
                    "template_data",
                    "tool_call",
                    "tool_call__task_definition",
                    "tool_call__task_definition_version__task_definition",
                ).order_by("pk"),
            )
        )
        .get(pk=pk)
    )


# ---------------------------------------------------------------------------
# Section sidebars
# ---------------------------------------------------------------------------

def _sidebar_keys(section: str, context: dict[str, Any]) -> tuple[str, ...]:
    from webui.views.common import flatten_session_tree

    if section in ("dashboard", "chats"):
        archived = "true" if context.get("show_archived") else "false"
        keys = [
            f"SessionModel.root@is_archived:{archived}",
            "SessionModel@is_active:true",
            "Query",
            "AgentTaskCall",
            "Project.root",
        ]
        project_id = context.get("sidebar_project_id")
        if project_id:
            keys.append(
                f"SessionModel.root@project:{project_id}@is_archived:{archived}"
            )
        for session in flatten_session_tree(context.get("sidebar_sessions") or []):
            keys.append(f"SessionModel:{session.pk}")
            keys.append(
                f"SessionModel.parent_session:{session.pk}@is_archived:{archived}"
            )
        return tuple(keys)
    if section == "agents":
        return ("AgentModel", "Project.root")
    if section == "projects":
        return ("Project",)
    if section == "workspaces":
        return ("WorkspaceModel",)
    if section == "skills":
        return ("SkillModel",)
    if section == "cron":
        return ("Cronjob",)
    if section == "collections":
        return ("DataCollection",)
    if section == "workitems":
        return ("WorkItem", "Project")
    if section == "memory":
        return ("Project", "WorkItem")
    if section == "insights":
        return ("ApiProvider", "AiModel")
    return ()


def _build_section_sidebar(section: str):
    def build(request, pk, params):
        from webui.views.common import (
            SIDEBAR_TEMPLATES,
            component_sidebar_url,
            sidebar_context,
        )

        context = sidebar_context(request, section, active_id=None)
        context.update(
            {
                "section": section,
                "sidebar_template": SIDEBAR_TEMPLATES[section],
                "sidebar_base_url": component_sidebar_url(section, {}),
            }
        )
        return ComponentData(context, _sidebar_keys(section, context))

    return build


# ---------------------------------------------------------------------------
# Chat components
# ---------------------------------------------------------------------------

def _build_chat_header(request, pk, params):
    from webui.views.chat import _header_context

    session = _session(pk)
    context = _header_context(session)
    return ComponentData(
        context,
        (f"SessionModel:{pk}", f"Query.session:{pk}"),
    )


def _build_chat_thread(request, pk, params):
    from webui.chat_cards import build_chat_cards
    from webui.thread import DEFAULT_LIMIT, build_thread

    session = _session(pk)
    limit = _int(params.get("limit"), DEFAULT_LIMIT)
    limit = max(1, min(limit, 2000))
    around = _int(params.get("around"), None)
    rows = build_thread(session, limit=limit, end_pk=around)

    from server.models.message import Message

    total = Message.objects.filter(session=session)
    if around is not None:
        total = total.filter(pk__lte=around)
    try:
        total_messages = total.count()
    except Exception:  # pylint: disable=broad-exception-caught
        total_messages = len(rows)

    context = {
        "session": session,
        "rows": rows,
        "thread_limit": limit,
        "thread_around": around,
        "thread_has_older": total_messages > limit,
        "thread_older_limit": min(limit + DEFAULT_LIMIT, 2000),
        "cards": build_chat_cards(session),
    }
    return ComponentData(
        context,
        (
            f"Message.session:{pk}",
            f"Query.session:{pk}",
            f"Response.session:{pk}",
            f"AgentTaskCall.session:{pk}",
            f"SessionModel:{pk}",
        ),
    )


def _build_chat_message(request, pk, params):
    from webui.thread import _message_row

    message = _message(pk)
    row = _message_row(message)
    session = message.session
    keys = [f"Message:{pk}", f"MessagePart.message:{pk}"]
    for part in message.parts.all():
        call_id = getattr(part, "tool_call_id", None)
        if call_id:
            keys.append(f"AgentTaskCall:{call_id}")
    return ComponentData(
        {"row": row, "session": session},
        tuple(keys),
        immutable=not session.is_active,
    )


def _build_chat_query(request, pk, params):
    from server.models.queries.query import Query, QueryStatus
    from webui.thread import Row

    query = Query.objects.select_related("session").get(pk=pk)
    response = query.related_response.order_by("-pk").first()
    row = Row("query", query, response=response)
    return ComponentData(
        {"row": row, "session": query.session},
        (
            f"Query:{pk}",
            f"Query.session:{query.session_id}",
            f"Response.query:{pk}",
        ),
        immutable=query.status != QueryStatus.ACTIVE,
    )


def _build_chat_response(request, pk, params):
    from server.models.queries.response import Response, ResponseStatus
    from webui.markdown import render_markdown
    from webui.thread import Row

    response = Response.objects.select_related("session").get(pk=pk)
    row = Row(
        "response",
        response,
        body_html=render_markdown(response.content or ""),
        reasoning=response.reasoning or "",
    )
    return ComponentData(
        {"row": row, "session": response.session},
        (
            f"Response:{pk}",
            f"Response.session:{response.session_id}",
        ),
        immutable=response.status != ResponseStatus.ACTIVE,
    )


def _build_chat_toc(request, pk, params):
    from webui.views.common import compaction_segments

    session = _session(pk)
    return ComponentData(
        {"session": session, "toc_segments": compaction_segments(session)},
        (f"Message.session:{pk}",),
    )


def _build_chat_composer(request, pk, params):
    from webui.views.common import (
        command_options,
        composer_config,
        composer_state,
        send_key,
    )

    session = _session(pk)
    context = {"session": session, "send_key": send_key(), "commands": command_options(session)}
    context.update(composer_config(session))
    context.update(composer_state(session))
    # The footer is its own live element; the form itself must not be swapped
    # away while the user is typing.
    return ComponentData(context)


def _build_chat_panel(request, pk, params):
    from webui.views.chat import _panel_context

    session = _session(pk)
    tab = params.get("tab") or "details"
    context = _panel_context(session, tab, request)
    return ComponentData(context)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _int(raw, default):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SECTIONS_WITH_SIDEBARS = (
    "dashboard",
    "chats",
    "agents",
    "projects",
    "workspaces",
    "skills",
    "cron",
    "collections",
    "workitems",
    "memory",
    "insights",
    "logs",
    "settings",
)

for _section in SECTIONS_WITH_SIDEBARS:
    register(
        ComponentSpec(
            name=f"{_section}-sidebar",
            template="webui/shell/_sidebar.html",
            build=_build_section_sidebar(_section),
            url_name=f"{_section}_sidebar",
        )
    )

register(ComponentSpec("chat-header", "webui/chat/_header.html", _build_chat_header))
register(ComponentSpec("chat-thread", "webui/chat/_thread.html", _build_chat_thread))
register(ComponentSpec("chat-message", "webui/chat/_message.html", _build_chat_message))
register(ComponentSpec("chat-query", "webui/chat/_query.html", _build_chat_query))
register(ComponentSpec("chat-response", "webui/chat/_response.html", _build_chat_response))
register(ComponentSpec("chat-toc", "webui/chat/_toc.html", _build_chat_toc))
register(ComponentSpec("chat-composer", "webui/chat/_composer.html", _build_chat_composer))
register(ComponentSpec("chat-panel", "webui/chat/_panel.html", _build_chat_panel))
