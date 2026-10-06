"""Browser configuration.

Read from the ``browser:`` block of ``~/.agentone/config.yaml``, merged over
:data:`DEFAULTS`.  This module deliberately avoids importing Django or
``runtime.settings.settings`` so the daemon can run as a plain Python
process; the YAML is read directly.  Unknown keys are ignored and invalid
values fall back to the default.

Example::

    browser:
      mode: headful          # headful | headless
      minimize: false        # best-effort window minimize (macOS: unsupported)
      scope: session         # session | named (per-call override wins)
      max_processes: 6
      idle_seconds: 900
      ephemeral_by_default: false
      block_images: false
      humanize: 1.5
      enable_cache: true
      nav_timeout: 45
      action_timeout: 15
      audit: true
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    # Headful is the default: a real window makes login/CAPTCHA completion
    # possible and matches "one more window is fine".
    "mode": "headful",
    # Camoufox/Playwright expose no supported minimize on macOS. Best-effort
    # minimizing via osascript needs Accessibility permission, so it is opt-in
    # and defaults to off rather than firing a permission prompt.
    "minimize": False,
    "scope": "session",
    "max_processes": 6,
    "idle_seconds": 900,
    "ephemeral_by_default": False,
    "block_images": False,
    "humanize": 1.5,
    "enable_cache": True,
    "nav_timeout": 45,
    "action_timeout": 15,
    "audit": True,
    # Domain policy is intentionally permissive for now (allow-all); the audit
    # log below is the record of what was visited. Allow/deny lists can be
    # layered on later without changing the tool surface.
    "allow_domains": [],
    "deny_domains": [],
}

_VALID_MODES = {"headful", "headless"}


def _config_path() -> Path:
    configured = os.environ.get("AGENTONE_CONFIG_FILE", "").strip()
    if configured:
        return Path(os.path.expanduser(configured))
    return Path.home() / ".agentone" / "config.yaml"


def _read_section() -> dict:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
    except Exception:  # pylint: disable=broad-exception-caught
        return {}
    if not isinstance(loaded, dict):
        return {}
    section = loaded.get("browser")
    return section if isinstance(section, dict) else {}


def _clamp(section: dict) -> dict:
    merged = {**DEFAULTS}
    for key, default in DEFAULTS.items():
        value = section.get(key, default)
        if isinstance(default, bool):
            merged[key] = value if isinstance(value, bool) else default
        elif isinstance(default, int):
            merged[key] = value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else default
        elif isinstance(default, float):
            merged[key] = value if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0 else default
        elif isinstance(default, list):
            merged[key] = [str(v) for v in value] if isinstance(value, (list, tuple)) else default
        else:
            merged[key] = value if isinstance(value, str) and value else default
    if merged["mode"] not in _VALID_MODES:
        merged["mode"] = DEFAULTS["mode"]
    if merged["scope"] not in {"session", "named"}:
        merged["scope"] = DEFAULTS["scope"]
    return merged


def get_browser_config() -> dict:
    """Return the merged browser configuration."""
    return _clamp(_read_section())


def headless() -> bool:
    return get_browser_config()["mode"] == "headless"
