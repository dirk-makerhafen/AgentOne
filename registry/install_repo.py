"""
Install repos for content-addressed version tracking.

Each scope (global, per-project) gets a single git repo under
``~/.agentone/install/``. Source files are synced (rsync) from the
``.agentone/`` directory into the install repo, then versioned via git.

Version identifiers are **git tree SHAs** for each manifest folder
(``scripts.md``, ``agent.md``, ``skill.md`` parent directory). Tree SHAs
are deterministic — same content always produces the same hash, regardless
of commit timestamp or history.

At runtime, files are extracted from install repos into
``~/.agentone/runtime/<version_pk>/`` so that ``BoundTask.call()`` imports
the exact versioned copy, not whatever is on disk in the source tree.
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

        # Extract a file at a specific tree SHA:
        repo.checkout_file(tree_sha="abc123", filename="delegate_task.py",
                           dest=Path("/tmp/runtime/42"))
    """

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path.resolve()
        self.source_root: Optional[Path] = None

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def for_global(cls, source_root: Optional[Path] = None) -> "InstallRepo":
        """Create the global install repo at ``INSTALL_BASE / "global"``."""
        repo = cls(repo_path=INSTALL_BASE / "global")
        if source_root is not None:
            repo.source_root = source_root.resolve()
        return repo

    @classmethod
    def for_project(cls, project_name: str,
                    source_root: Optional[Path] = None) -> "InstallRepo":
        """Create a per-project install repo at ``INSTALL_BASE / "project_{name}"``."""
        safe = project_name.replace(" ", "_").replace("/", "_")
        repo = cls(repo_path=INSTALL_BASE / f"project_{safe}")
        if source_root is not None:
            repo.source_root = source_root.resolve()
        return repo

    @classmethod
    def for_task_definition_version(cls, tdv: object) -> "InstallRepo":
        """Resolve the install repo that owns *tdv*.

        Inspects ``tdv.task_definition.parent_project`` to decide global vs
        per-project.
        """
        parent_project = getattr(getattr(tdv, "task_definition", None),
                                 "parent_project", None)
        if parent_project is not None:
            return cls.for_project(project_name=parent_project.name)
        return cls.for_global()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sync(self) -> None:
        """Copy source files into the install repo and auto-commit."""
        if self.source_root is None:
            raise RuntimeError("source_root is required for sync()")
        self._ensure_repo()
        self._copy_files()
        self._auto_commit()

    def tree_sha(self, source_dir: Path) -> str:
        """Return the git tree SHA for *source_dir* (a path under ``source_root``).

        The tree SHA is deterministic: identical folder content always
        produces the same hash across different commits or machines.
        """
        if self.source_root is None:
            raise RuntimeError("source_root is required for tree_sha()")
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

    def checkout_tree(self, tree_sha: str, dest: Path) -> Path:
        """Extract **all files** from *tree_sha* into *dest* directory.

        The *tree_sha* is the tree SHA of the manifest folder (the ``commit``
        field on a ``TaskDefinitionVersion``). Every file in that folder is
        extracted, so sibling imports (e.g. ``from .helpers import x``) work.

        Returns *dest*.
        """
        if not self._git_available():
            raise RuntimeError("git is required for runtime file extraction")

        result = subprocess.run(
            ["git", "-C", str(self.repo_path), "archive", "--format=tar",
             tree_sha],
            capture_output=True,
        )
        if result.returncode != 0:
            raise FileNotFoundError(
                f"Tree {tree_sha[:12]} not found in {self.repo_path} "
                f"(stderr: {result.stderr.strip()})"
            )
        dest.mkdir(parents=True, exist_ok=True)
        import tarfile
        import io
        with tarfile.open(fileobj=io.BytesIO(result.stdout)) as tar:
            tar.extractall(path=dest)
        return dest

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
        ``shutil.copytree``.
        """
        assert self.source_root is not None
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
