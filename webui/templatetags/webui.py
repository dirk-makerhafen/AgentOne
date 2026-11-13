"""Small template filters used by the htmx fragments."""

from __future__ import annotations

import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static as static_url
from django.utils import timezone

from webui.markdown import render_markdown

register = template.Library()


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


@register.filter(name="markdown")
def markdown_filter(value) -> str:
    """Render *value* as sanitised markdown (cached)."""
    return render_markdown(str(value or ""))


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
