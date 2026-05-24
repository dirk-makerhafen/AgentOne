"""
Runtime version folders — versioned copies of tool/script files.

Each ``~/.agentone/runtime/<version_pk>/`` folder holds the **full file tree**
for one ``TaskDefinitionVersion``. The entire manifest folder is extracted
from the install repo at the version's tree SHA, so sibling imports
(e.g. ``from .helpers import x``) work correctly.

A ``.last_used`` file stores the Unix timestamp of the last access, enabling
periodic cleanup of stale folders.
"""

import os
import time
from pathlib import Path
from typing import Optional

from registry.install_repo import InstallRepo


RUNTIME_BASE = Path(os.path.expanduser("~/.agentone/runtime"))
STALE_SECONDS = 3600  # 1 hour — folders older than this are eligible for cleanup


class RuntimeFolder:
    """Manage a single runtime version folder.

    Usage::

        rf = RuntimeFolder(task_definition_version)
        folder_path = rf.ensure_folder()
        script_path = folder_path / "delegate_task.py"
    """

    def __init__(self, task_definition_version: object) -> None:
        self.tdv = task_definition_version
        self.folder = RUNTIME_BASE / str(task_definition_version.pk)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ensure_folder(self) -> Path:
        """Return the runtime folder path, re-extracting all files if missing.

        If the folder was cleaned up or never created, the entire tree is
        re-extracted from the install repo.
        """
        marker = self.folder / ".last_used"
        if not marker.exists():
            self._extract_tree()
        self._touch_last_used()
        return self.folder

    def mark_used(self) -> None:
        """Touch ``.last_used`` so the folder survives the next cleanup."""
        self._touch_last_used()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_tree(self) -> None:
        """Extract all files from the install repo at this version's tree SHA."""
        commit = getattr(self.tdv, "commit", "")
        if not commit:
            raise RuntimeError(
                f"TaskDefinitionVersion {self.tdv.pk} has no commit hash"
            )

        repo = InstallRepo.for_task_definition_version(self.tdv)
        # Remove any partial leftovers before extracting
        if self.folder.exists():
            _rmtree(self.folder)
        repo.checkout_tree(tree_sha=commit, dest=self.folder)

    def _touch_last_used(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        stamp = self.folder / ".last_used"
        stamp.write_text(str(int(time.time())))

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def last_used_time(cls, folder: Path) -> Optional[int]:
        """Return the Unix timestamp from ``.last_used`` in *folder*, or *None*."""
        stamp = folder / ".last_used"
        if stamp.exists():
            try:
                return int(stamp.read_text().strip())
            except (ValueError, OSError):
                return None
        return None

    @classmethod
    def collect_garbage(cls, max_age_seconds: int = STALE_SECONDS) -> int:
        """Remove all runtime folders whose ``.last_used`` is older than
        *max_age_seconds*.

        Returns the number of folders removed.
        """
        if not RUNTIME_BASE.exists():
            return 0
        now = int(time.time())
        removed = 0
        for entry in sorted(RUNTIME_BASE.iterdir()):
            if not entry.is_dir():
                continue
            lu = cls.last_used_time(entry)
            if lu is not None and (now - lu) > max_age_seconds:
                _rmtree(entry)
                removed += 1
        return removed


def _rmtree(path: Path) -> None:
    """Safely remove a directory tree."""
    import shutil
    shutil.rmtree(path, ignore_errors=True)
