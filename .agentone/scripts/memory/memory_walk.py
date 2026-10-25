"""Walk every memory root and (re)generate ``.memory_sources.md`` manifests."""

from __future__ import annotations


def memory_walk(write: bool = True, refresh: bool = False):
    """Walk every existing memory root and update ``.memory_sources.md``.

    Scans all memory roots (global, per-workspace, per-project, per-agent)
    for ``.memory_sources.md`` manifests.  Rebuilds any that are missing or
    out of date, recording git commit hashes so future runs can detect
    changes.

    Args:
        write: When ``True`` (default), actually writes/updates manifest
            files on disk.  When ``False``, only computes what *would* be
            written — useful for dry-run inspection.
        refresh: When ``True``, queries the database for the newest
            REFLECTION and COMPACTION messages across all sessions and
            saves any that are not already present as report files in the
            corresponding task memory directories.  This is useful after
            a session has produced new reflection/compaction output that
            hasn't been persisted to the filesystem yet.

    Returns:
        ``(success, result)`` — on success, *result* is the summary dict
        from :func:`runtime.memory.tree.walk_memory`.  When ``refresh=True``
        the dict also includes ``reflections_written`` and
        ``compactions_written`` counts.  On failure, *result* is a dict
        with an ``"error"`` key.
    """
    from runtime.memory.tree import walk_memory

    try:
        return True, walk_memory(write=write, refresh=refresh)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"error": str(exc)}
