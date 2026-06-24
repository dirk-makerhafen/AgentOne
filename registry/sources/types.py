"""Data types for upstream manifest sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class SourceConfig:
    """A single upstream source (git repo) for manifest files.

    Attributes
    ----------
    repo:
        Git clone URL (https or ssh).
    ref:
        Branch, tag, or commit SHA to track.
    include:
        Optional list of glob patterns to filter which subdirectories
        are synced.  When empty all content under the upstream's
        ``.agentone/`` is included.
    """

    repo: str
    ref: str = "main"
    include: List[str] = field(default_factory=list)


@dataclass
class SourceResult:
    """Result of syncing one upstream source."""

    name: str
    repo: str
    ref: str
    status: str  # "cloned" | "updated" | "up to date" | "error"
    error: str = ""
