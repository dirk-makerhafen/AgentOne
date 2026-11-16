"""Small template filters used by the htmx fragments."""

from __future__ import annotations

import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static as static_url
from django.utils import timezone
from django.utils.safestring import mark_safe

from webui.core.markdown import render_markdown

register = template.Library()


@register.simple_tag(takes_context=True, name="component")
def component_tag(context, name, pk=None, **params):
    """Render one independently cacheable component.

    Inline (full document) mode emits the rendered element with its own SSE
    trigger; htmx mode emits a placeholders that loads from the component URL
    and is preserved across parent swaps.
    """
    from webui.core.components import render_component_ref

    return render_component_ref(context, name, pk, params)


@register.simple_tag(name="static_v")
def static_v(path: str) -> str:
    """Static URL with an mtime cache-buster.

    Whitenoise caches non-hashed asset names, so a browser can keep serving an
    old ``app.js`` after a deploy.  Appending the file mtime makes the URL
    change whenever the asset does.
    """
    url = static_url(path)
    try:
        mtime = int(os.path.getmtime(finders.find(path)))
    except (TypeError, OSError):
        return url
    return f"{url}?v={mtime}"


@register.filter(name="get_item")
def get_item(mapping, key):
    """Look up *key* in a dict from a template (``mapping|get_item:key``)."""
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter(name="markdown", is_safe=True)
def markdown_filter(value) -> str:
    """Render *value* as sanitised markdown (cached)."""
    return mark_safe(render_markdown(str(value or "")))


@register.filter(name="reltime")
def reltime(value) -> str:
    """Compact relative time: ``now``, ``4m``, ``3h``, ``2d``, ``5w``, ``1y``."""
    if not value:
        return ""
    try:
        seconds = (timezone.now() - value).total_seconds()
    except Exception:  # pylint: disable=broad-exception-caught
        return ""
    if seconds < 0:
        return "now"
    if seconds < 60:
        return "now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    if seconds < 7 * 86400:
        return f"{int(seconds // 86400)}d"
    if seconds < 365 * 86400:
        return f"{int(seconds // (7 * 86400))}w"
    return f"{int(seconds // (365 * 86400))}y"


@register.filter(name="intcomma")
def intcomma(value) -> str:
    """Format an integer with thousands separators (``1,234``)."""
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        return f"{int(number):,}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


@register.filter(name="clock")
def clock(value) -> str:
    """Wall-clock time in the active timezone (``HH:MM``)."""
    if not value:
        return ""
    try:
        value = timezone.localtime(value)
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        return value.strftime("%H:%M")
    except Exception:  # pylint: disable=broad-exception-caught
        return ""
