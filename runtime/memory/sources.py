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
    ".memory_state.json",
    ".memory_queue.json",
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


def hash_files(paths: Iterable[Path], base: Path | None = None) -> str | None:
    """Return ``sha256:<hex>`` over *paths* (sorted, metadata excluded).

    Only regular files are included.  Relative names (to *base*) are hashed
    before each file's bytes so renames are visible.  Returns ``None`` when
    the resulting set is empty.
    """
    base_path = Path(base) if base is not None else None
    files = [
        Path(p)
        for p in paths
        if Path(p).is_file() and not is_metadata_path(Path(p))
    ]
    if not files:
        return None

    def _sort_key(path: Path) -> str:
        return _rel_name(path, base_path)

    digest = hashlib.sha256()
    for path in sorted(files, key=_sort_key):
        digest.update(_rel_name(path, base_path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _rel_name(path: Path, base: Path | None) -> str:
    if base is None:
        return path.as_posix()
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


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


def source_key(source: dict[str, Any]) -> str:
    """Return the path identity used to preserve last-processed hashes."""
    return str(source.get("path", ""))


def source_identity(source: dict[str, Any]) -> tuple[str, int] | None:
    """Return ``(kind, pk)`` for a project/workspace source, if present."""
    kind = str(source.get("kind") or "").strip()
    pk = source.get("pk")
    if not kind or pk is None:
        return None
    try:
        return kind, int(pk)
    except (TypeError, ValueError):
        return None


def previous_hashes(manifest: dict[str, Any]) -> dict[str, Any]:
    """Map source path to its ``last_processed_hash`` from *manifest*."""
    out: dict[str, Any] = {}
    for source in manifest.get("sources") or []:
        if isinstance(source, dict):
            out[source_key(source)] = source.get("last_processed_hash")
    return out


def previous_by_identity(manifest: dict[str, Any]) -> dict[tuple[str, int], Any]:
    """Map child-scope ``(kind, pk)`` to ``last_processed_hash``."""
    out: dict[tuple[str, int], Any] = {}
    for source in manifest.get("sources") or []:
        if not isinstance(source, dict):
            continue
        identity = source_identity(source)
        if identity is not None:
            out[identity] = source.get("last_processed_hash")
    return out
