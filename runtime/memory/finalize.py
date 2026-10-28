"""Programmatic completion for synthesized memory nodes.

A synthesizer writes ``memory.md`` / ``reflection.md`` and then ends its turn.
The harness — not the LLM — advances the node's manifest: ``memory_merge``
schedules the ``memory_finalize`` task with the synthesizer's task call as its
argument, so the framework auto-awaits the child session and hands its
``final_result`` to this module.  Keeping the write and the manifest advance in
separate, harness-owned steps means a failed run can never mark a node current.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.memory import paths as mempaths
from runtime.memory import sources as memsources

#: Files a synthesis run must produce before the manifest may advance.
OUTPUT_FILES = ("memory.md", "reflection.md")

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
            at least one output file must have been written after that moment,
            so a failed run cannot advance a manifest using stale output.

    Returns:
        ``(True, {...})`` when the manifest advanced, otherwise
        ``(False, {"status": "error", "message": ...})``.
    """
    from runtime.memory.tree import mark_processed

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

    written = [name for name in OUTPUT_FILES if (path / name).is_file()]
    if not written:
        return False, {
            "status": "error",
            "message": (
                f"no memory output found in {path}; write memory.md and "
                "reflection.md before marking the node processed"
            ),
        }

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
            if not fresh:
                return False, {
                    "status": "error",
                    "message": (
                        f"no output written since synthesis started in {path}; "
                        "the node stays pending"
                    ),
                    "files": written,
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
