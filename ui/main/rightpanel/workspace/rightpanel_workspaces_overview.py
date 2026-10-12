"""Workspaces dashboard right panel.

The dashboard manages the *collection* of workspaces, so it embeds the plural
``workspaces_assistant`` chat (global scope) rather than the singular
``workspace_assistant`` that the single-workspace right panel uses. The panel
itself lives in :mod:`ui.main.rightpanel.assistant_chat` alongside every other
entity's assistant panel; this module re-exports it so existing imports keep
working.
"""
from __future__ import annotations

from ui.main.rightpanel.assistant_chat import RightPanelWorkspacesOverview

__all__ = ["RightPanelWorkspacesOverview"]
