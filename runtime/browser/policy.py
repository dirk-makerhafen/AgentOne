"""Navigation policy and the navigation audit trail.

Domain policy is deliberately permissive for now: ``allow_domains`` empty means
allow-all, and ``deny_domains`` is an optional floor.  Every navigation is
appended to ``~/.agentone/browser/nav-audit.jsonl`` so a permissive default is
still accountable.  Tightening the allowlist later needs no tool-surface
change — only config.
"""

from __future__ import annotations

import json
import threading
import time
from urllib.parse import urlparse

from runtime.browser import paths

_audit_lock = threading.Lock()


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _matches(host: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        p = str(pattern).strip().lower().lstrip(".")
        if not p:
            continue
        if host == p or host.endswith("." + p):
            return True
    return False


def check_navigation(url: str, cfg: dict) -> tuple[bool, str]:
    """Return ``(allowed, reason)`` for a navigation to *url*.

    Only web URLs and ``about:`` are permitted.  ``file:`` is deliberately
    excluded: the browser runs as the user, so navigating to a local path would
    let a page render arbitrary local files and hand them back through
    ``snapshot``/``read`` — bypassing the workspace file guardrails, which only
    govern the explicit path arguments.  ``data:`` is excluded for the same
    reason: it can only ever render attacker-chosen markup, never a real page.
    """
    if not url.startswith(("http://", "https://", "about:")):
        return False, f"unsupported URL scheme: {url}"
    host = _host(url)
    deny = list(cfg.get("deny_domains") or [])
    if host and _matches(host, deny):
        return False, f"domain {host} is on the browser deny list"
    allow = list(cfg.get("allow_domains") or [])
    if allow and host and not _matches(host, allow):
        return False, f"domain {host} is not on the browser allow list"
    return True, ""


def audit_navigation(
    url: str,
    scope: dict,
    *,
    page_id: str | None = None,
    kind: str = "navigate",
    cfg: dict | None = None,
) -> None:
    """Append one navigation to the audit log (best effort, never raises).

    *scope* is the server-derived scope dict sent by the tool, so the log
    records which session and which profile the visit came from.
    """
    settings = cfg if cfg is not None else {}
    if not settings.get("audit", True):
        return
    entry = {
        "ts": time.time(),
        "kind": kind,
        "url": url,
        "host": _host(url),
        "session_pk": scope.get("session_pk"),
        "root_pk": scope.get("root_pk"),
        "profile_key": scope.get("profile_key"),
        "page_id": page_id,
    }
    try:
        with _audit_lock:
            paths.ensure_private_dir(paths.browser_base())
            with open(paths.audit_log_path(), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry) + "\n")
    except Exception:  # pylint: disable=broad-exception-caught
        pass
