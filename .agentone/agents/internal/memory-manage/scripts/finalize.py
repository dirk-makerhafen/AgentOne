"""Programmatic completion for synthesized memory nodes.

Two synthesizers — one per output file — write ``memory.md`` and
``reflections.md`` and then end their turns. The harness — not the LLM —
advances the node's manifest: ``memory_merge`` schedules the ``memory_finalize``
task with both synthesizer task calls as arguments, so the framework auto-awaits
both child sessions before this module validates and advances the manifest.
Keeping the writes and the manifest advance in separate, harness-owned steps
means a failed or half-finished run can never mark a node current.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import paths as mempaths
import sources as memsources

#: Files a synthesis run must produce before the manifest may advance.
OUTPUT_FILES = ("memory.md", "reflections.md")

#: Allow for coarse filesystem timestamps when comparing an output write to the
#: moment the synthesizer was dispatched.
MTIME_SLACK_SECONDS = 2.0


def finalize_memory(
    target_dir: Any,
    *,
    started_at: float | str | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Validate a synthesized node and advance its ``.memory_sources.md``.

    Args:
        target_dir: Directory containing the node's manifest and output files.
        started_at: Unix timestamp when synthesis was dispatched.  When given,
            both output files must have been written after that moment, so a
            failed or half-finished run cannot advance a manifest.

    Returns:
        ``(True, {...})`` when the manifest advanced, otherwise
        ``(False, {"status": "error", "message": ...})``.
    """
    from tree import mark_processed

    raw = str(target_dir or "").strip()
    if not raw:
        return False, {"status": "error", "message": "target_dir is required"}

    path = Path(raw).expanduser()
    try:
        path = path.resolve()
    except OSError as exc:
        return False, {"status": "error", "message": f"invalid target_dir: {exc}"}

    if not path.is_dir():
        return False, {
            "status": "error",
            "message": f"target_dir does not exist: {path}",
        }

    manifest = path / memsources.SOURCES_FILENAME
    if not manifest.is_file():
        return False, {
            "status": "error",
            "message": (
                f"no {memsources.SOURCES_FILENAME} in {path}; "
                "run memory_walk before synthesizing"
            ),
        }

    missing = [name for name in OUTPUT_FILES if not (path / name).is_file()]
    if missing:
        return False, {
            "status": "error",
            "message": (
                f"missing memory output in {path}: {', '.join(missing)}; "
                "write memory.md and reflections.md before marking the node processed"
            ),
        }
    written = list(OUTPUT_FILES)

    if started_at is not None:
        try:
            cutoff = float(started_at) - MTIME_SLACK_SECONDS
        except (TypeError, ValueError):
            cutoff = None
        if cutoff is not None:
            fresh = []
            for name in written:
                try:
                    if (path / name).stat().st_mtime >= cutoff:
                        fresh.append(name)
                except OSError:
                    continue
            if len(fresh) != len(written):
                stale = [name for name in written if name not in fresh]
                return False, {
                    "status": "error",
                    "message": (
                        f"output not written since synthesis started in {path}: "
                        f"{', '.join(stale)}; the node stays pending"
                    ),
                    "files": written,
                    "stale": stale,
                }

    try:
        if not mark_processed(path):
            return False, {
                "status": "error",
                "message": f"{path} is not a node in the memory tree",
            }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"status": "error", "message": f"mark_processed failed: {exc}"}

    try:
        mempaths.inflight_path(path).unlink(missing_ok=True)
    except OSError:
        pass

    return True, {
        "status": "success",
        "target_dir": path.as_posix(),
        "files": written,
        "message": "manifest advanced; this node is now current",
    }
