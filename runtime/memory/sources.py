"""``.memory_sources.md`` manifest helpers.

Each memory node (scope root, agent, task) gets a generated, gitignored
manifest describing the files it consumes and the git commit seen at the
last successful synthesis.  The walker in :mod:`runtime.memory.tree` owns
writing these files; synthesis agents never write them.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import frontmatter
import yaml

SOURCES_FILENAME = ".memory_sources.md"

_METADATA_NAMES = {
    SOURCES_FILENAME,
    ".gitignore",
    ".DS_Store",
}
_METADATA_SUFFIXES = (".pyc", ".pyo")
_METADATA_DIRS = {".git", "__pycache__"}


def is_metadata_path(path: Path) -> bool:
    """Return whether *path* is walker/git metadata, not memory content."""
    path = Path(path)
    if path.name in _METADATA_NAMES or path.name.endswith(_METADATA_SUFFIXES):
        return True
    return any(part in _METADATA_DIRS for part in path.parts)


def read_sources(path: Path) -> dict[str, Any]:
    """Return the manifest frontmatter at *path* (empty dict when absent)."""
    try:
        data = frontmatter.load(Path(path))
    except (OSError, UnicodeError, ValueError):
        return {}
    return dict(data.metadata or {})


def _without_generated_at(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k != "generated_at"}


def render_sources(payload: dict[str, Any]) -> str:
    """Render *payload* as YAML frontmatter plus a human-readable table."""
    data = dict(payload)
    data.setdefault("generated_at", datetime.now().astimezone().isoformat(timespec="seconds"))
    front = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
    lines = ["---", front, "---", "", "# Memory sources", ""]
    sources = data.get("sources") or []
    if not sources:
        lines.append("_No sources._")
    else:
        lines.append("| Path | Last processed | Current | Hours | Changed chars | Status |")
        lines.append("|---|---|---|---|---|---|")
        for source in sources:
            last = source.get("last_processed_hash")
            current = source.get("current_hash")
            if current is None:
                status = "missing"
            elif last is None:
                status = "pending"
            elif last == current:
                status = "current"
            else:
                status = "pending"
            path = _cell(source.get("path", ""))
            last_cell = _cell(last) if last else "—"
            current_cell = _cell(current) if current else "—"
            hours = source.get("hours_since_processed")
            changed = source.get("changed_chars")
            hours_cell = _cell(hours) if hours is not None else "—"
            changed_cell = _cell(changed) if changed is not None else "—"
            lines.append(
                f"| {path} | {last_cell} | {current_cell} | "
                f"{hours_cell} | {changed_cell} | {status} |"
            )
    lines.append("")
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def write_sources(path: Path, payload: dict[str, Any]) -> bool:
    """Atomically write *payload* to *path*; return whether the file changed.

    ``generated_at`` is ignored when deciding whether the file needs a
    rewrite, so repeated walks do not touch unchanged manifests.
    """
    path = Path(path)
    old = read_sources(path)
    if _without_generated_at(old) == _without_generated_at(payload):
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(render_sources(payload), encoding="utf-8")
    os.replace(tmp, path)
    return True


def previous_hashes(manifest: dict[str, Any]) -> dict[str, Any]:
    """Map source path to its ``last_processed_hash`` from *manifest*."""
    out: dict[str, Any] = {}
    for source in manifest.get("sources") or []:
        if isinstance(source, dict):
            out[str(source.get("path", ""))] = source.get("last_processed_hash")
    return out


def previous_by_identity(manifest: dict[str, Any]) -> dict[int, Any]:
    """Map child-scope ``pk`` to ``last_processed_hash`` for path-change tracking."""
    out: dict[int, Any] = {}
    for source in manifest.get("sources") or []:
        if not isinstance(source, dict):
            continue
        pk = source.get("pk")
        if pk is not None:
            try:
                out[int(pk)] = source.get("last_processed_hash")
            except (TypeError, ValueError):
                pass
    return out
