from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

# A page longer than this is truncated in the tool result and cached in the
# calling session's private folder instead (see ``_session_cache_dir``).
MAX_CONTENT_CHARS = 15_000
# When truncating, keep 75% of the budget from the start and 25% from the end
# (the end often holds the conclusion/summary). Both ends snap to line breaks.
HEAD_RATIO = 0.75

# Data URIs are noise for a text-only LLM: markdownify turns inline base64
# images into ``![](data:image/png;base64,...)``, which is billed as text.
_DATA_URI_RE = re.compile(r"data:[A-Za-z0-9.+/-]+[,;][^\s\"')\]]+", re.IGNORECASE)


def _clean_html(html: str) -> str:
    """Remove page chrome and inline binary blobs before converting to text."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Fallback for environments without markdownify's bs4 dependency.
        return re.sub(r"(?is)<(script|style|noscript|svg|template)\b.*?</\1\s*>", "", html)

    soup = BeautifulSoup(html, "html.parser")
    # Mintlify hides its whole site config in a <template id="mint-config">;
    # markdownify would otherwise render it as ~85% of the page.
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()

    for img in soup.find_all("img"):
        src = str(img.get("src") or "")
        if src.lower().startswith("data:"):
            # Keep the alt text so the model still knows an image was there.
            alt = " ".join(str(img.get("alt") or "image").split())[:120] or "image"
            img.replace_with(f"[{alt} omitted]")

    for node in soup.find_all(True):
        for attr in ("src", "href", "poster"):
            value = node.get(attr)
            if isinstance(value, str) and value.lower().startswith("data:"):
                node[attr] = "#"
    return str(soup)


def _session_cache_dir(session: Any | None) -> Path | None:
    """Return ``<session private dir>/cache``, or None outside a session."""
    if session is None:
        env_dir = os.environ.get("AGENTONE_SESSION_DIR")
        return Path(env_dir) / "cache" if env_dir else None
    try:
        from runtime.session_folder import ensure_session_dir

        return ensure_session_dir(session) / "cache"
    except Exception:  # pylint: disable=broad-exception-caught
        # Never turn a cache-write failure into a failed fetch.
        return None


def _cache_path(cache_dir: Path, url: str) -> Path:
    """Deterministic, human-readable cache filename for a URL."""
    parsed = urlsplit(url)
    label = re.sub(r"[^A-Za-z0-9]+", "-", f"{parsed.netloc}{parsed.path}")
    label = label.strip("-")[:80].rstrip("-") or "page"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return cache_dir / "webfetch" / f"{label}-{digest}.md"


def _omitted_marker(omitted_chars: int) -> str:
    return f"\n\n… {omitted_chars:,} characters omitted from the middle of this page …\n\n"


def _cache_footer(
    path: str | None,
    original_chars: int,
    error: str | None = None,
    max_chars: int = MAX_CONTENT_CHARS,
) -> str:
    """Footer embedded in the returned content so the model always sees it."""
    if path:
        return (
            f"\n[FULL PAGE: {original_chars:,} chars saved to {path}. "
            "Use filesystem.read(path, offset, limit) or "
            "filesystem.grep(path=..., pattern=...) to inspect the omitted "
            "sections instead of re-fetching.]\n"
        )
    if error:
        return (
            f"\n[Page truncated to {max_chars:,} chars from "
            f"{original_chars:,}; full page could not be saved: {error}]\n"
        )
    return (
        f"\n[Page truncated to {max_chars:,} chars from "
        f"{original_chars:,}; no session cache is available outside an agent session.]\n"
    )


def _truncate_head_tail(content: str, max_chars: int, footer: str = "") -> str:
    """Return 75% head + 25% tail, newline-snapped, with an omission marker."""
    if len(content) <= max_chars:
        return content

    # Reserve space using the longest marker we could need, so the result plus
    # footer never exceeds ``max_chars``.
    budget = max_chars - len(footer) - len(_omitted_marker(len(content)))
    if budget < 100:
        budget = max(20, max_chars // 2)
    head_chars = int(budget * HEAD_RATIO)
    tail_chars = budget - head_chars

    head = content[:head_chars]
    newline = head.rfind("\n")
    if newline > head_chars // 2:
        head = head[:newline + 1]

    tail = content[-tail_chars:] if tail_chars else ""
    newline = tail.find("\n")
    if 0 <= newline < tail_chars // 2:
        tail = tail[newline + 1:]

    omitted = len(content) - len(head) - len(tail)
    return head + _omitted_marker(omitted) + tail + footer


def webFetch(_session: Any | None, url: str, format: str = "markdown", max_chars: int = MAX_CONTENT_CHARS) -> tuple[bool, dict]:
    '''
    Fetches content from a specified URL.

    - Takes a URL and optional format as input.
    - Fetches the URL content, converts to requested format
      (markdown by default), then drops scripts, styles and inline
      base64 images so only useful text reaches the LLM.
    - Pages longer than ``max_chars`` (15,000 by default) are returned as
      75% head + 25% tail (newline-snapped), with an explicit omission
      marker and a footer pointing at the full text saved under
      ``<session private dir>/cache/webfetch/``. Use filesystem.read or
      filesystem.grep on that path to inspect omitted sections.
    - Use this tool when you need to retrieve and analyze web
      content.
    - The URL must be a fully-formed valid URL.
    - HTTP URLs will be automatically upgraded to HTTPS.

    Args:
        url: The URL to fetch content from.
        format: The format to return the content in ("text",
            "markdown", or "html"). Default: "markdown".
        max_chars: Maximum number of characters returned inline.

    Returns:
        A tuple of (success, result).
        On success, result contains:
            - status: "success"
            - content: str (possibly truncated)
            - url: str
            - truncated: bool
            - original_chars: int (only when truncated)
            - full_content_path: str (only when truncated and a session
              folder is available)
            - hint: str (only when truncated)
        On error, result contains:
            - status: "error"
            - message: str
    '''
    try:
        if not url:
            return (False, {'status': 'error', 'message': 'URL not provided'})

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        headers = {
            'User-Agent': 'AgentOne/1.0',
        }

        response = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
        response.raise_for_status()

        if format == "html":
            # Explicit raw-HTML requests are kept verbatim.
            content = response.text
        elif format == "text":
            cleaned = _clean_html(response.text)
            content = re.sub(r'<[^>]+>', '', cleaned)
            content = re.sub(r'\n\s*\n', '\n\n', content).strip()
            content = _DATA_URI_RE.sub('[data URI omitted]', content)
        else:
            cleaned = _clean_html(response.text)
            try:
                import markdownify
                content = markdownify.markdownify(cleaned, heading_style="ATX")
            except ImportError:
                import re as _re
                content = _re.sub(r'<[^>]+>', '', cleaned).strip()
            content = _DATA_URI_RE.sub('[data URI omitted]', content)

        result = {
            'status': 'success',
            'content': content,
            'url': url,
            'truncated': False,
        }
        if len(content) > max_chars:
            saved_path: str | None = None
            cache_error: str | None = None
            cache_dir = _session_cache_dir(_session)
            if cache_dir is not None:
                try:
                    path = _cache_path(cache_dir, url)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        os.chmod(path.parent, 0o700)
                    except OSError:
                        pass
                    path.write_text(content, encoding="utf-8")
                    saved_path = str(path)
                    result['full_content_path'] = saved_path
                    result['hint'] = (
                        f"Full page ({len(content):,} chars) saved to {saved_path}. "
                        "Use filesystem.read(path, offset, limit) or "
                        "filesystem.grep(path=..., pattern=...) to inspect "
                        "specific sections instead of re-fetching."
                    )
                except OSError as exc:
                    cache_error = str(exc)
                    result['hint'] = (
                        f"Page truncated to {max_chars:,} of {len(content):,} chars; "
                        f"could not cache the full page: {exc}"
                    )
            else:
                result['hint'] = (
                    f"Page truncated to {max_chars:,} of {len(content):,} chars; "
                    "no session cache is available outside an agent session."
                )

            truncated = _truncate_head_tail(
                content,
                max_chars,
                _cache_footer(saved_path, len(content), cache_error, max_chars),
            )
            result.update(
                content=truncated,
                truncated=True,
                original_chars=len(content),
                returned_chars=len(truncated),
            )
        return (True, result)

    except httpx.RequestError as e:
        return (False, {'status': 'error', 'message': f'Failed to fetch {url}: {str(e)}'})
    except Exception as e:
        import traceback
        return (False, {'status': 'error', 'message': f'Error fetching {url}: {str(e)}\n{traceback.format_exc()}'})

if __name__ == '__main__':
    import argparse
    import json

    parser = argparse.ArgumentParser(description='Fetch content from a URL.')
    parser.add_argument('url', help='URL to fetch.')
    parser.add_argument('--format', default='markdown', choices=['text', 'markdown', 'html'], help='Output format.')
    parser.add_argument('--max-chars', type=int, default=MAX_CONTENT_CHARS, help='Max characters returned inline.')
    args = parser.parse_args()

    success, result = webFetch(None, url=args.url, format=args.format, max_chars=args.max_chars)
    if success:
        print(result.get('content', ''))
        if result.get('hint'):
            print(f"[{result['hint']}]", file=sys.stderr)
    else:
        print(json.dumps(result, indent=2))
    exit(0 if success else 1)
