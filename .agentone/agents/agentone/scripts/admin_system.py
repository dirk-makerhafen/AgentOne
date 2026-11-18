"""Framework-wide actions for admin_tool, notably manifest reload.

Manifest-defined entities (agents, skills) only become live in the database
after ``run_reload_all`` re-reads their ``.agentone/`` tree. This module gives
the agent a callable framework reload instead of relying on a shell command.
"""
from __future__ import annotations

from typing import Any

from admin_common import _default_reload_folder, _err, _ok


def _system(session: Any, action: str, kwargs: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    if action == "reload":
        folder = str(kwargs.get("folder") or _default_reload_folder(session))
        try:
            from registry.management.commands.reload_all import run_reload_all

            result = run_reload_all(folder)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return _err(f"Reload failed: {e}", folder=folder)
        if result["status"] == "error":
            return _err(result["summary"], folder=folder)
        return result["status"] == "success", {
            "status": result["status"],
            "folder": folder,
            "summary": result["summary"],
            "counts": result["counts"],
            "details": result["details"],
            "errors": result["errors"],
        }

    return _err(f"Unknown action '{action}' for scope 'system'")
