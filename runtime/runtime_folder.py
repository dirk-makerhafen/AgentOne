"""
Runtime version folders — versioned copies of tool/script files.

Each ``~/.agentone/runtime/<version_pk>/`` folder holds the **full file tree**
for one ``TaskDefinitionVersion``. The entire manifest folder is extracted
from the install repo at the version's tree SHA, so sibling imports
(e.g. ``from .helpers import x``) work correctly.

A ``.last_used`` file stores the Unix timestamp of the last access, enabling
periodic cleanup of stale folders.
"""

import time
from pathlib import Path
from typing import Optional

from registry.install_repo import InstallRepo
from runtime.paths import runtime_base as _runtime_base


def _base() -> Path:
    return _runtime_base()


RUNTIME_BASE = _runtime_base()
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
        self.folder = _base() / str(task_definition_version.pk)

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
        """Extract all files from the install repo at this version's tree SHA.

        Falls back to copying the task's source folder from disk when the
        pinned commit is no longer available in the install repo (e.g. after
        a rebuild that orphaned older ``TaskDefinitionVersion`` rows).  This
        keeps pinned sessions runnable instead of hard-failing.
        """
        commit = getattr(self.tdv, "commit", "")
        repo = InstallRepo.for_task_definition_version(self.tdv)
        # Remove any partial leftovers before extracting
        if self.folder.exists():
            _rmtree(self.folder)
        if commit:
            try:
                repo.checkout_tree(tree_sha=commit, dest=self.folder)
                return
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        self._extract_from_source()

    def _extract_from_source(self) -> None:
        """Copy the task's source folder from disk (fallback path)."""
        import shutil

        source_dir = self._resolve_source_dir()
        if source_dir is None or not source_dir.is_dir():
            raise RuntimeError(
                f"TaskDefinitionVersion {self.tdv.pk} has no resolvable source folder"
            )
        self.folder.mkdir(parents=True, exist_ok=True)
        for item in source_dir.iterdir():
            dest = self.folder / item.name
            if item.is_dir():
                if dest.exists():
                    _rmtree(dest)
                shutil.copytree(item, dest, symlinks=True)
            elif item.is_file():
                shutil.copy2(item, dest)

    def _resolve_source_dir(self) -> "Path | None":
        from pathlib import Path

        td = getattr(self.tdv, "task_definition", None)

        # Prefer the stored source file path: it points at the exact manifest
        # folder the version was loaded from, regardless of how the (possibly
        # hyphenated) group label maps to the on-disk directory layout.
        path = getattr(self.tdv, "path", None)
        if not path and td is not None:
            path = getattr(td, "path", None)
        if path:
            candidate = Path(str(path)).expanduser()
            source = candidate.parent if candidate.suffix or candidate.is_file() else candidate
            if source.is_dir():
                return source
            # Fall through to the group-based heuristics below when the
            # stored path no longer exists on disk.

        if td is None:
            return None
        group = (getattr(td, "group_name", "") or "").strip()
        parent_agent = getattr(td, "parent_agent", None)
        parent_project = getattr(td, "parent_project", None)
        parent_skill = getattr(td, "parent_skill", None)
        if parent_agent is not None:
            manifest_dir = getattr(parent_agent, "manifest_dir", "") or ""
            if not manifest_dir:
                try:
                    from runtime.paths import agentone_root

                    manifest_dir = (agentone_root() / "agents" / parent_agent.name).as_posix()
                except Exception:  # pylint: disable=broad-exception-caught
                    manifest_dir = ""
            if manifest_dir:
                base = Path(manifest_dir).expanduser() / "scripts"
                # Try the group as a direct subdir first, then a nested path
                # derived from a hyphenated group label (e.g. "filesystem-write"
                # -> "filesystem/write").
                for candidate_group in (group, group.replace("-", "/") if group else group):
                    if not candidate_group:
                        return base
                    candidate = base / candidate_group
                    if candidate.is_dir():
                        return candidate
                return base / group if group else base
        if parent_project is not None:
            try:
                from runtime.paths import project_manifest_dir

                manifest_dir = getattr(parent_project, "agentone_dir", "") or project_manifest_dir(parent_project).as_posix()
            except Exception:  # pylint: disable=broad-exception-caught
                manifest_dir = getattr(parent_project, "agentone_dir", "") or ""
            if manifest_dir:
                base = Path(manifest_dir).expanduser() / "scripts"
                for candidate_group in (group, group.replace("-", "/") if group else group):
                    if not candidate_group:
                        return base
                    candidate = base / candidate_group
                    if candidate.is_dir():
                        return candidate
                return base / group if group else base
        if parent_skill is not None:
            manifest_dir = getattr(parent_skill, "manifest_dir", "") or ""
            if manifest_dir:
                base = Path(manifest_dir).expanduser() / "scripts"
                for candidate_group in (group, group.replace("-", "/") if group else group):
                    if not candidate_group:
                        return base
                    candidate = base / candidate_group
                    if candidate.is_dir():
                        return candidate
                return base / group if group else base
        try:
            from runtime.paths import agentone_root

            base = agentone_root() / "scripts"
            for candidate_group in (group, group.replace("-", "/") if group else group):
                if not candidate_group:
                    return base
                candidate = base / candidate_group
                if candidate.is_dir():
                    return candidate
            return base / group if group else base
        except Exception:  # pylint: disable=broad-exception-caught
            return None
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
        base = _base()
        if not base.exists():
            return 0
        now = int(time.time())
        removed = 0
        for entry in sorted(base.iterdir()):
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
