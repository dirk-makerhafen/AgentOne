"""Import helper for the memory-manage script library.

The memory modules live inside the ``memory-manage`` agent manifest under
``.agentone/agents/internal/memory-manage/scripts/memory_lib`` so the agent's
scripts and their library ship (and version) together.  That folder is not a
Python package path, so add it to ``sys.path`` before importing ``memory_lib``.
"""

from __future__ import annotations

import sys
from pathlib import Path

MEMORY_SCRIPTS = (
    Path(__file__).resolve().parents[2]
    / ".agentone"
    / "agents"
    / "internal"
    / "memory-manage"
    / "scripts"
)

if str(MEMORY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(MEMORY_SCRIPTS))

import finalize  # noqa: E402
import git  # noqa: E402
import improvements  # noqa: E402
import paths  # noqa: E402
import playbook  # noqa: E402
import sources  # noqa: E402
import tree  # noqa: E402

__all__ = [
    "MEMORY_SCRIPTS",
    "finalize",
    "git",
    "improvements",
    "paths",
    "playbook",
    "sources",
    "tree",
]
