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

# ``<body hx-boost>`` upgrades same-origin links to a partial swap.  That is
# only correct for in-app pages: a markdown link to a download or an asset must
# keep its normal browser behaviour instead of swapping bytes into the shell.
_LINK_HREF = re.compile(r'<a\s+href="([^"]*)"')
_BOOSTABLE_PREFIXES = ("/app/", "#")

_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title", "width", "height"},
    "code": {"class"},
    "pre": {"class"},
    "th": {"align"},
    "td": {"align"},
}

_URL_SCHEMES = {"http", "https", "mailto"}


def _neutralise_non_app_links(html: str) -> str:
    """Keep ``hx-boost`` away from links that are not in-app pages."""

    def replace(match: re.Match[str]) -> str:
        href = match.group(1)
        if href.startswith(_BOOSTABLE_PREFIXES) or href.startswith(("http", "mailto:")):
            return match.group(0)
        return f'{match.group(0)} hx-boost="false"'

    return _LINK_HREF.sub(replace, html)


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
    return _EXTERNAL_LINK.sub(r'<a target="_blank" href="\1"', _neutralise_non_app_links(html))
