"""Walk every memory root and (re)generate ``.memory_sources.md`` manifests."""

from __future__ import annotations


def memory_walk(_session=None, **kwargs):
    """Generate source manifests for all existing memory nodes.

    Set ``write=False`` to only report pending/missing sources without
    touching the filesystem.
    """
    from runtime.memory.tree import walk_memory

    write = bool(kwargs.pop("write", True))
    try:
        return True, walk_memory(write=write)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return False, {"error": str(exc)}
