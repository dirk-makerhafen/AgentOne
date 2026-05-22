"""
Install repos for content-addressed version tracking.

Each scope (global, per-project) gets a single git repo under
``~/.agentone/install/``. Source files are synced (rsync) from the
``.agentone/`` directory into the install repo, then versioned via git.

Version identifiers are **git tree SHAs** for each manifest folder
(``scripts.md``, ``agent.md``, ``skill.md`` parent directory). Tree SHAs
are deterministic — same content always produces the same hash, regardless
of commit timestamp or history.
"""

import hashlib
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional


INSTALL_BASE = Path(os.path.expanduser("~/.agentone/install"))


class InstallRepo:
    """A single git repo tracking one scope's manifest files.

    Usage::

        repo = InstallRepo.for_global(
            source_root=Path("/project/.agentone"),
        )
        repo.sync()
        sha = repo.tree_sha(Path("/project/.agentone/scripts/subagent"))
        # → git rev-parse HEAD:scripts/subagent
    """

    def __init__(self, repo_path: Path, source_root: Path) -> None:
        self.repo_path = repo_path.resolve()
        self.source_root = source_root.resolve()

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def for_global(cls, source_root: Path) -> "InstallRepo":
        """Create the global install repo at ``INSTALL_BASE / "global"``."""
        return cls(repo_path=INSTALL_BASE / "global", source_root=source_root)

    @classmethod
    def for_project(cls, project_name: str, source_root: Path) -> "InstallRepo":
        """Create a per-project install repo at ``INSTALL_BASE / "project_{name}"``."""
        safe = project_name.replace(" ", "_").replace("/", "_")
        return cls(repo_path=INSTALL_BASE / f"project_{safe}", source_root=source_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sync(self) -> None:
        """Copy source files into the install repo and auto-commit."""
        self._ensure_repo()
        self._copy_files()
        self._auto_commit()

    def tree_sha(self, source_dir: Path) -> str:
        """Return the git tree SHA for *source_dir* (a path under ``source_root``).

        The tree SHA is deterministic: identical folder content always
        produces the same hash across different commits or machines.
        """
        try:
            rel = source_dir.resolve().relative_to(self.source_root)
        except ValueError:
            return self._fallback_hash(source_dir)

        if not self._git_available():
            return self._fallback_hash(source_dir)

        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"HEAD:{rel.as_posix()}"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return self._fallback_hash(source_dir)
        return result.stdout.strip()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_repo(self) -> None:
        """git init + configure identity if the repo doesn't exist yet."""
        if not self._git_available():
            return

        git_dir = self.repo_path / ".git"
        if not git_dir.exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=self.repo_path,
                capture_output=True,
            )

        for key, val in [
            ("user.name", "agentone-loader"),
            ("user.email", "loader@agentone.local"),
        ]:
            subprocess.run(
                ["git", "config", key, val],
                cwd=self.repo_path,
                capture_output=True,
            )

    def _copy_files(self) -> None:
        """Sync *source_root* contents into *repo_path*.

        Uses ``rsync -a --delete`` when available, falls back to
        ``shutil.copytree(dirs_exist_ok=True)``.
        """
        self.repo_path.mkdir(parents=True, exist_ok=True)

        if shutil.which("rsync"):
            subprocess.run(
                ["rsync", "-a", "--delete", "--checksum",
                 "--exclude=.git",
                 f"{self.source_root}/",
                 f"{self.repo_path}/"],
                capture_output=True,
            )
        else:
            for item in self.source_root.iterdir():
                dest = self.repo_path / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest, symlinks=True)
                elif item.is_file():
                    shutil.copy2(item, dest)

    def _auto_commit(self) -> None:
        """``git add -A`` then commit if anything is dirty.

        Handles the initial commit (no HEAD) correctly.
        """
        if not self._git_available():
            return

        subprocess.run(
            ["git", "add", "-A"],
            cwd=self.repo_path,
            capture_output=True,
        )

        # Check whether HEAD exists yet
        has_head = (
            subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
            ).returncode
            == 0
        )

        needs_commit = False
        if not has_head:
            needs_commit = True
        else:
            result = subprocess.run(
                ["git", "diff-index", "--cached", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                needs_commit = True

        if needs_commit:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            subprocess.run(
                ["git", "commit", "--quiet", "-m", f"sync {timestamp}"],
                cwd=self.repo_path,
                capture_output=True,
            )

    def _git_available(self) -> bool:
        try:
            subprocess.run(
                ["git", "--version"],
                capture_output=True, text=True, check=True,
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def _fallback_hash(self, source_dir: Path) -> str:
        """SHA-256 of all file contents in *source_dir* when git is unavailable."""
        content_hash = hashlib.sha256()
        for f in sorted(source_dir.rglob("*")):
            if f.is_file():
                content_hash.update(f.read_bytes())
        content_hash.update(str(time.time()).encode())
        return content_hash.hexdigest()[:40]
