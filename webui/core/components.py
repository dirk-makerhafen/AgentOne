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
    already loaded: component wrappers carry ``hx-preserve`` and htmx moves the
    live element into the new fragment by id.

    Container builders may set ``inline_children=True`` in their context to
    render children inline even for ``render=htmx`` responses.  Use this for
    list/thread containers that would otherwise fan out many placeholder loads
    on a full container refetch (e.g. SSE reset/reconnect).

Cache policy
------------

* Live components (they have observable keys) are ``private, no-cache`` with
  an ETag.  ``app.js`` sends ``If-None-Match`` together with
  ``X-AgentOne-ETag: 1``; an unchanged component answers ``204`` so htmx skips
  the swap and the browser keeps focus and open ``<details>``.  A browser's own
  cache revalidation has no marker and always gets a full ``200`` body — a lazy
  fragment must never answer ``204`` on its first load and stay empty.
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
    "HX_DISINHERIT",
    "component_url",
    "render_component",
    "render_component_ref",
    "render_fragment",
    "section_sidebar",
]


#: Attributes htmx inherits from an ancestor when the element itself does not
#: define them.  A component wrapper owns ``hx-swap``/``hx-sync`` for its *own*
#: request; without ``hx-disinherit`` every link and form inside the wrapper
#: also inherits them.  That is how a boosted child link ended up sharing the
#: wrapper's ``hx-sync`` and being aborted by the wrapper's SSE refetch, and
#: how a nested form could swap into the wrapper's target.
#:
#: ``hx-boost`` is deliberately absent: links inside components must keep
#: inheriting boost from ``<body>``.  Never use ``hx-disinherit="*"`` for the
#: same reason.
INHERITED_ATTRIBUTES = (
    "hx-confirm",
    "hx-encoding",
    "hx-params",
    "hx-prompt",
    "hx-push-url",
    "hx-replace-url",
    "hx-select",
    "hx-select-oob",
    "hx-swap",
    "hx-sync",
    "hx-target",
)

HX_DISINHERIT = " ".join(INHERITED_ATTRIBUTES)


@dataclass
class ComponentData:
    """Everything one component render needs from the domain layer."""

    context: dict[str, Any]
    keys: tuple[str, ...] = ()
    immutable: bool = False
    # When True, the component also refetches on SSE reconnect/reset. Disable for
    # leaf items that are fully rebuilt by a parent container's reset.
    reset: bool = True


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


def _is_client_revalidation(request, etag: str) -> bool:
    """Only honour ETags sent by our own htmx client, not browser cache probes.

    Live fragments use ``private, no-cache``, so a browser may revalidate them
    itself on a later page load.  A bare ``204`` would make htmx skip the first
    swap of a lazily loaded fragment (the detail pane would stay "Loading…").
    ``app.js`` marks its conditional GETs with ``X-AgentOne-ETag``; only those
    revalidations may skip the swap.
    """
    return (
        request.headers.get("If-None-Match") == etag
        and request.headers.get("X-AgentOne-ETag") == "1"
    )


def render_fragment(
    request,
    template_name: str,
    context: dict[str, Any] | None = None,
    *,
    status: int = 200,
) -> HttpResponse:
    """Render a small live fragment with the same ETag contract as components.

    Ad-hoc fragments (composer footer, panel body, polling output, kanban board)
    sit inside an element that owns its own ``hx-get``/``hx-trigger``.  They
    cannot use the component wrapper, but they still must not be swapped when
    their HTML did not change: an SSE refresh that replaces a button row on
    every task-call event makes the controls flicker.

    ``app.js`` remembers the ETag of every GET response by request path and
    sends it back as ``If-None-Match`` with ``X-AgentOne-ETag: 1``.  An unchanged
    fragment therefore answers ``204`` and htmx leaves the live DOM (and focus)
    alone; browser-native revalidation still gets the full body.
    """
    html = render_to_string(template_name, context or {}, request=request)
    etag = _etag(html)

    response = HttpResponse()
    response["Vary"] = "Cookie, X-AgentOne-ETag"
    response["Cache-Control"] = "private, no-cache"
    response["ETag"] = etag
    if _is_client_revalidation(request, etag):
        response.status_code = 204
        response["Content-Length"] = "0"
        return response

    response.status_code = status
    response.content = html
    response["Content-Length"] = str(len(response.content))
    return response


def _trigger(keys: tuple[str, ...], *, reset: bool = True) -> str:
    if not keys:
        return ""
    parts = [f"sse:{key} delay:150ms" for key in keys]
    if reset:
        parts.append("sse:reset delay:150ms")
    return ", ".join(parts)


def _open_tag(
    name: str,
    pk: int | None,
    params: dict[str, Any],
    *,
    etag: str | None = None,
    keys: tuple[str, ...] = (),
    reset: bool = True,
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
        # htmx checks ``hx-disinherit`` on the element that *owns* the inherited
        # attribute, not on this wrapper.  An ancestor with ``hx-target`` (the
        # tool card's detail pane, a composer form, ...) would otherwise capture
        # this wrapper's SSE refetch and replace that ancestor instead of itself.
        'hx-target="this"',
        f'hx-disinherit="{HX_DISINHERIT}"',
    ]
    if etag and not placeholder:
        attrs.append(f'data-component-etag="{escape(etag)}"')
    # hx-preserve keeps an already-loaded component alive when a parent swap
    # re-renders and emits a placeholder for it (htmx 2 moves the preserved old
    # element into the new fragment by id).  htmx 2's preserve pass would also
    # pantry a self-targeted outerHTML swap when the response carries the same
    # preserved id (placeholder load, SSE/reset refetch), which drops the element
    # or discards the response; webui/static/webui/app.js removes the target id
    # in htmx:beforeSwap to prevent that.  Do not remove that workaround.
    attrs.append("hx-preserve")
    if placeholder:
        attrs.append('hx-trigger="load, intersect once"')
    else:
        trigger = _trigger(keys, reset=reset)
        if trigger:
            attrs.append(f'hx-trigger="{escape(trigger)}"')
        else:
            # htmx defaults to `click` for an hx-get element with no explicit
            # trigger.  Keyless/immutable wrappers would then refetch on every
            # bubbled click from a child (e.g. a panel tab button), replacing
            # the subtree with stale server state.  Use an event we never send.
            attrs.append('hx-trigger="agentone:none"')
    return "<div " + " ".join(attrs) + ">"


def _wrap(
    name: str,
    pk: int | None,
    params: dict[str, Any],
    inner: str,
    *,
    etag: str | None,
    keys: tuple[str, ...],
    reset: bool = True,
    placeholder: bool = False,
) -> str:
    if placeholder and name.endswith("-sidebar"):
        # The boosted shell is asserted to contain the sidebar landmark even
        # before the component request settles.
        inner = '<aside class="sidebar" id="sidebar"></aside>'
    return _open_tag(
        name, pk, params, etag=etag, keys=keys, reset=reset, placeholder=placeholder
    ) + inner + "</div>"


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
    # ``render=full`` always inlines children.  ``render=htmx`` emits child
    # placeholders unless the builder opts into inline children (useful for
    # list/thread containers that would otherwise fan out many placeholder loads).
    inline_children = data.context.get("inline_children")
    context["component_inline"] = full or bool(inline_children)
    html = render_to_string(spec.template, context, request=request)
    keys = () if data.immutable else _collect_keys(data)

    response = HttpResponse()
    response["Vary"] = "Cookie, X-AgentOne-ETag"
    if data.immutable:
        response["Cache-Control"] = "private, max-age=31536000, immutable"
    else:
        response["Cache-Control"] = "private, no-cache"

    etag = _etag(html)
    response["ETag"] = etag
    if not data.immutable and _is_client_revalidation(request, etag):
        response.status_code = 204
        return response

    response.content = _wrap(
        name, pk, params, html, etag=etag, keys=keys, reset=bool(getattr(data, "reset", True))
    )
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
                reset=bool(getattr(data, "reset", True)),
            )
        )
    return mark_safe(_wrap(name, pk, params, "", etag=None, keys=(), reset=True, placeholder=True))



# ---------------------------------------------------------------------------
# Section sidebar helper (used by feature modules)
# ---------------------------------------------------------------------------

def build_section_sidebar(section: str, keys_fn):
    """Build function for a standard section sidebar component."""
    def build(request, pk, params):
        from webui.core.layout import SIDEBAR_TEMPLATES, component_sidebar_url, sidebar_context

        context = sidebar_context(request, section, active_id=None)
        context.update(
            {
                "section": section,
                "sidebar_template": SIDEBAR_TEMPLATES[section],
                "sidebar_base_url": component_sidebar_url(section, {}),
            }
        )
        return ComponentData(context, tuple(keys_fn(context)))

    return build


def register_section_sidebar(section: str, keys_fn):
    register(
        ComponentSpec(
            name=f"{section}-sidebar",
            template="layout/_sidebar_frame.html",
            build=build_section_sidebar(section, keys_fn),
            url_name=f"{section}_sidebar",
        )
    )


# ---------------------------------------------------------------------------
# Feature component registration
# ---------------------------------------------------------------------------

def register_feature_components():
    """Import feature modules so they register their components/sidebars."""
    from webui.features.chats.components import register_chat_components
    from webui.features.chats import sidebar as chats_sidebar
    from webui.features.dashboard import sidebar as dashboard_sidebar
    from webui.features.agents import sidebar as agents_sidebar
    from webui.features.projects import sidebar as projects_sidebar
    from webui.features.workspaces import sidebar as workspaces_sidebar
    from webui.features.skills import sidebar as skills_sidebar
    from webui.features.cron import sidebar as cron_sidebar
    from webui.features.collections import sidebar as collections_sidebar
    from webui.features.workitems import sidebar as workitems_sidebar
    from webui.features.memory import sidebar as memory_sidebar
    from webui.features.insights import sidebar as insights_sidebar
    from webui.features.logs import sidebar as logs_sidebar
    from webui.features.settings import sidebar as settings_sidebar

    register_chat_components()
    chats_sidebar.register_sidebar_component("chats")
    dashboard_sidebar.register_sidebar_component()
    agents_sidebar.register_sidebar_component()
    projects_sidebar.register_sidebar_component()
    workspaces_sidebar.register_sidebar_component()
    skills_sidebar.register_sidebar_component()
    cron_sidebar.register_sidebar_component()
    collections_sidebar.register_sidebar_component()
    workitems_sidebar.register_sidebar_component()
    memory_sidebar.register_sidebar_component()
    insights_sidebar.register_sidebar_component()
    logs_sidebar.register_sidebar_component()
    settings_sidebar.register_sidebar_component()


register_feature_components()
