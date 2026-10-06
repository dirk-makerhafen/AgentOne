"""Camoufox launch + stable-profile persistence.

Identity stability
------------------
Camoufox draws a fingerprint (navigator, screen, fonts, WebGL, voices, audio
seed, …) on each launch.  Redrawing on every reopen would make one persistent
profile look like a different machine every time, which is both a detection
tell and confusing for logins.  So the generated options are written once to
``<profile>/launch_options.json`` and replayed with
``NewBrowser(from_options=...)`` on every subsequent launch.  ``refresh_identity``
forces a redraw.

Launch shape
------------
``persistent_context=True`` is used so cookies/logins/localStorage live in
Firefox's on-disk ``user_data`` directory.  With Playwright's sync API a single
``sync_playwright()`` instance is thread-bound, so the daemon starts Playwright
once on its driver thread and calls :func:`launch` per browser process against
that shared instance.
"""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

from runtime.browser import paths

#: Host platform names mapped to Camoufox fingerprint OS names.
_HOST_OS_BY_PLATFORM = {
    "Darwin": "macos",
    "Linux": "linux",
    "Windows": "windows",
}

#: Keys we keep when persisting launch options. Everything Camoufox returns is
#: JSON-serializable, but trimming keeps the file readable and drops the
#: transient ``args`` override list when it is empty.
_DROP = {"args"}


class BrowserMissing(RuntimeError):
    """Raised when the Camoufox package or its browser build is unavailable."""


def host_os_key() -> str | None:
    """Return the Camoufox OS name for the current host, if it is known."""
    return _HOST_OS_BY_PLATFORM.get(platform.system())


def ensure_launch_options(profile_key: str, cfg: dict, *, refresh: bool = False) -> dict[str, Any]:
    """Return the persisted Camoufox launch options for *profile_key*.

    Generates them on first use (or when *refresh* is set), writes them
    ``0600``, and returns them for :func:`launch`.  New identities are drawn
    for the host OS so the claimed platform, fonts, and native font handling
    stay coherent; already-persisted identities are left unchanged.
    """
    options_path = paths.launch_options_path(profile_key)
    if options_path.exists() and not refresh:
        try:
            options = json.loads(options_path.read_text(encoding="utf-8"))
            if isinstance(options, dict) and options.get("executable_path"):
                return options
        except (OSError, ValueError):
            pass  # regenerate below

    # Lazy: the package and its browser build are optional at import time.
    # pylint: disable=import-outside-toplevel
    try:
        from camoufox.utils import launch_options
    except ImportError as exc:  # pragma: no cover - depends on install
        raise BrowserMissing(
            "camoufox is not installed. Install it with 'pip install camoufox' "
            "then fetch a browser build with 'python3 -m camoufox fetch'."
        ) from exc

    try:
        options = launch_options(
            headless=cfg.get("mode") == "headless",
            humanize=cfg.get("humanize"),
            enable_cache=bool(cfg.get("enable_cache")),
            block_images=bool(cfg.get("block_images")),
            os=host_os_key(),
            i_know_what_im_doing=True,
        )
    except BrowserMissing:
        raise
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise BrowserMissing(
            f"Camoufox could not build launch options: {exc}. "
            "If this is a missing browser build, run 'python3 -m camoufox fetch'."
        ) from exc

    options = {k: v for k, v in options.items() if k not in _DROP or v}
    options["user_data_dir"] = str(paths.user_data_dir(profile_key))

    profile_dir = paths.ensure_private_dir(paths.profile_dir(profile_key))
    paths.ensure_private_dir(Path(options["user_data_dir"]))
    tmp = profile_dir / "launch_options.json.tmp"
    tmp.write_text(json.dumps(options, indent=2, sort_keys=True), encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(options_path)
    return options


def launch(playwright: Any, profile_key: str, cfg: dict, *, refresh: bool = False) -> Any:
    """Launch a persistent Camoufox context on *playwright*.

    Returns a Playwright ``BrowserContext`` (the persistent-context shape).
    """
    options = ensure_launch_options(profile_key, cfg, refresh=refresh)
    # pylint: disable=import-outside-toplevel
    try:
        from camoufox.sync_api import NewBrowser
    except ImportError as exc:  # pragma: no cover - depends on install
        raise BrowserMissing(
            "camoufox is not installed. Install it with 'pip install camoufox'."
        ) from exc
    return NewBrowser(playwright, from_options=options, persistent_context=True)


def browser_installed() -> bool:
    """True when both the package and a browser build appear usable."""
    # pylint: disable=import-outside-toplevel
    try:
        from camoufox.utils import launch_path
    except ImportError:
        return False
    try:
        return bool(launch_path())
    except Exception:  # pylint: disable=broad-exception-caught
        return False
