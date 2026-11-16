"""Sidebar panel for workspaces, rendered as a path-derived tree.

Only :func:`build_workspace_tree` survives the removal of pyHtmlGui; the view
classes have been removed.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ui.main.workspace.workspace import norm_workspace_path, workspace_parent_map


def _norm(path: str) -> str:
    """Normalize a workspace path for prefix comparison."""
    return norm_workspace_path(path)


def build_workspace_tree(items: list) -> list[dict]:
    """Build DFS-ordered tree rows from workspace-like objects.

    Each item needs ``pk``, ``name`` and ``path`` attributes (``color`` is
    optional and defaults to "").  Returns a flat list of row dicts
    (``pk``, ``name``, ``path``, ``display_path``, ``color``, ``depth``,
    ``has_children``) in pre-order: parents before children, siblings
    sorted by name (roots) or by name within a parent.
    """
    by_pk = {}
    for ws in items:
        by_pk[ws.pk] = ws

    parent_of = workspace_parent_map(items)
    normed = {ws.pk: _norm(ws.path) for ws in items}

    children: dict[int | None, list] = {}
    for ws in items:
        children.setdefault(parent_of[ws.pk], []).append(ws)
    for siblings in children.values():
        siblings.sort(key=lambda w: (w.name or "").lower())

    rows: list[dict] = []

    def _walk(pk: int | None, depth: int, parent_path: str | None) -> None:
        for ws in children.get(pk, []):
            mine = normed[ws.pk]
            if parent_path and mine.startswith(parent_path + os.sep):
                display_path = os.path.relpath(mine, parent_path)
            else:
                display_path = ws.path
            rows.append(
                {
                    "pk": ws.pk,
                    "name": ws.name or mine,
                    "path": ws.path,
                    "display_path": display_path,
                    "color": getattr(ws, "color", "") or "",
                    "depth": depth,
                    "has_children": bool(children.get(ws.pk)),
                }
            )
            _walk(ws.pk, depth + 1, mine)

    _walk(None, 0, None)
    return rows