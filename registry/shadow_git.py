"""
Shadow git repos for independent folder-level version tracking.

Each folder with a manifest file (scripts.md, skill.md, agent.md) gets a
shadow git repository stored in a .shadowgit/ subdirectory. This provides
reliable content hashes independent of the parent project's git history.

On each load:
  - Init if .shadowgit/ doesn't exist
  - Stage all changes (git add -A)
  - Auto-commit if dirty
  - Return the HEAD commit hash
"""

import subprocess
import time
from pathlib import Path


def get_or_init_shadow_repo(folder: Path) -> str:
    """
    Ensure a shadow git repo exists at *folder*, auto-commit any changes,
    and return the current HEAD commit hash.

    If git is not available, falls back to a timestamp-based hash.
    """
    folder = folder.resolve()

    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True, text=True, check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _fallback_hash(folder)

    git_dir = folder / ".shadowgit"
    gitlink = folder / ".git"

    # Init if needed
    if not git_dir.exists():
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=folder, capture_output=True,
        )
        if gitlink.exists() and not gitlink.is_dir():
            pass
        elif gitlink.exists() and gitlink.is_dir():
            gitlink.rename(git_dir)
        if not gitlink.exists() or (gitlink.exists() and gitlink.is_dir()):
            gitlink.write_text(f"gitdir: {git_dir.relative_to(folder)}")

    # Configure minimal identity for auto-commits
    for key, val in [
        ("user.name", "agentone-loader"),
        ("user.email", "loader@agentone.local"),
    ]:
        subprocess.run(
            ["git", "config", key, val],
            cwd=folder, capture_output=True,
        )

    # Stage all changes
    subprocess.run(
        ["git", "add", "-A"],
        cwd=folder, capture_output=True,
    )

    # Check if anything changed since HEAD
    result = subprocess.run(
        ["git", "diff-index", "--cached", "HEAD"],
        cwd=folder, capture_output=True, text=True,
    )
    if result.stdout.strip():
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        subprocess.run(
            ["git", "commit", "--quiet", "-m", f"auto-snapshot {timestamp}"],
            cwd=folder, capture_output=True,
        )

    # Return HEAD hash
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=folder, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _fallback_hash(folder: Path) -> str:
    """Timestamp-based hash when git is not available."""
    import hashlib
    content_hash = hashlib.sha256()
    for f in sorted(folder.rglob("*")):
        if f.is_file() and ".shadowgit" not in f.parts:
            content_hash.update(f.read_bytes())
    content_hash.update(str(time.time()).encode())
    return content_hash.hexdigest()[:40]
