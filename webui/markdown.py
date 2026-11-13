"""Markdown rendering for chat messages, sanitised on the server.

The legacy UI rendered markdown in the browser with ``marked``.  Server-side
rendering keeps the htmx fragments self-contained (no per-swap JS) and lets us
sanitise LLM/tool output with ``nh3`` before it reaches the DOM.
"""

from __future__ import annotations

import re
from functools import lru_cache

import markdown as _markdown
import nh3

_MD = _markdown.Markdown(
    extensions=["fenced_code", "tables", "sane_lists"],
    output_format="html5",
)

# nh3 adds ``rel`` itself; we add ``target`` so links open in a new tab.
_EXTERNAL_LINK = re.compile(r'<a\s+href="(https?://[^"]+)"')

_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height"},
    "code": {"class"},
    "pre": {"class"},
    "th": {"align"},
    "td": {"align"},
}

_URL_SCHEMES = {"http", "https", "mailto"}


@lru_cache(maxsize=1024)
def render_markdown(text: str) -> str:
    """Return sanitised HTML for *text* (cached; safe to call per fragment)."""
    if not text:
        return ""
    html = _MD.reset().convert(text)
    html = nh3.clean(
        html,
        attributes=_ATTRIBUTES,
        url_schemes=_URL_SCHEMES,
        link_rel="noopener noreferrer",
    )
    # Only external links get a target; in-page anchors keep their behaviour.
    return _EXTERNAL_LINK.sub(r'<a target="_blank" href="\1"', html)
