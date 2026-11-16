"""Helpers for the WorkspaceModel ``access`` JSON field.

The Django/htmx web UI renders and edits access via
``webui/templates/webui/workspaces/_access_form.html`` and plain form posts handled by
``webui.views.workspaces``.
"""
from __future__ import annotations

SECTIONS = ("read", "write")
KEYS = ("allow", "ask", "deny")
DEFAULTS = ("allow", "ask", "deny")
# Unset/invalid defaults fall back to the runtime inside-default (allow),
# so saving an untouched workspace never narrows its policy.
FALLBACK_DEFAULT = "allow"


def normalize_access(raw: dict | None) -> dict:
    """Return a complete access dict (both sections, default + 3 lists)."""
    raw = raw if isinstance(raw, dict) else {}
    data: dict = {}
    for section in SECTIONS:
        sec = raw.get(section) if isinstance(raw.get(section), dict) else {}
        default = sec.get("default")
        if default not in DEFAULTS:
            default = FALLBACK_DEFAULT
        lists = {}
        for key in KEYS:
            vals = sec.get(key) or []
            if isinstance(vals, str):
                vals = [vals]
            lists[key] = [str(v) for v in vals if str(v).strip()]
        data[section] = {"default": default, **lists}
    return data
