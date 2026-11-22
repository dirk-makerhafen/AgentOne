"""Path-shape checks shared by guardrails and manifest validation.

Windows forms are recognised on *every* host.  A manifest authored on Windows
may be loaded on macOS/Linux; treating ``C:\\secrets\\key`` or ``\\\\server\\share``
as a relative path would skip policy validation entirely.
"""

from __future__ import annotations

import re

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")
_WINDOWS_ENV = re.compile(r"^%[^%\\/]+%")
_POSIX_ABSOLUTE = ("/", "~", "$HOME", "${HOME}")


def is_absolute(token: str) -> bool:
    """True for POSIX/Windows absolute, home-anchored and env-anchored paths."""
    value = token.strip()
    if not value:
        return False
    if value.startswith(_POSIX_ABSOLUTE):
        return True
    # Drive-absolute and drive-relative (C:foo) both escape a workspace root.
    if _WINDOWS_DRIVE.match(value):
        return True
    # UNC paths (\\server\share). A leading // is already POSIX-absolute.
    if value.startswith("\\\\"):
        return True
    # %USERPROFILE%\..., %TEMP%\... and PowerShell's $env:USERPROFILE\...
    if _WINDOWS_ENV.match(value) or value.lower().startswith("$env:"):
        return True
    return False


def has_traversal(pattern: str) -> bool:
    """True if any ``..`` segment is present, with either separator style."""
    return ".." in [part for part in re.split(r"[\\/]+", pattern.strip()) if part]


def is_device_node(token: str) -> bool:
    """True for POSIX ``/dev/`` nodes (which are not ordinary file targets)."""
    return token.strip().startswith("/dev/")
