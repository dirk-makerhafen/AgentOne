"""Git helpers for per-memory-directory repositories.

Each memory root (``~/.agentone/memory``, ``<agentone_dir>/memory``) gets its
own lightweight git repository so memory state can be versioned, diffed and
rolled back independently of the rest of the instance. Repos are local-only.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Optional


def _git_available() -> bool:
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True, text=True, check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=False)


_SHA_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


def is_git_hash(value: object) -> bool:
    """Return whether *value* looks like a git commit SHA (SHA-1 or SHA-256)."""
    return isinstance(value, str) and bool(_SHA_RE.fullmatch(value.strip()))


def repo_for(path: Path) -> Optional[Path]:
    """Return the nearest enclosing git work tree for *path*, if any."""
    probe = Path(path).resolve()
    if not probe.is_dir():
        probe = probe.parent
    while True:
        if (probe / ".git").exists():
            return probe
        if probe.parent == probe:
            return None
        probe = probe.parent


def _repo_rel(path: Path) -> tuple[Optional[Path], str]:
    repo = repo_for(path)
    if repo is None:
        return None, ""
    try:
        rel = Path(path).resolve().relative_to(repo).as_posix()
    except (OSError, ValueError):
        return repo, ""
    return repo, "" if rel == "." else rel


def path_commit(
    path: Path,
    files: Optional[list[Path]] = None,
    before: Optional[str] = None,
) -> Optional[str]:
    """Return the last commit SHA touching *path* or *files*.

    When *files* is given, only those paths are considered.  When *before*
    is given, history is cut at that commit.  ``HEAD`` is used when *path*
    is the repository root and *files* is not given.
    """
    repo, rel = _repo_rel(path)
    if repo is None:
        return None
    args = ["git", "log", "-1", "--format=%H"]
    if before:
        if not is_git_hash(before):
            return None
        args.append(before)
    if files is not None:
        rels = []
        for item in files:
            try:
                rels.append(Path(item).resolve().relative_to(repo).as_posix())
            except (OSError, ValueError):
                continue
        if not rels:
            return None
        args.extend(["--", *rels])
    elif rel:
        args.extend(["--", rel])
    result = _run(args, cwd=repo)
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else None


def commit_time(repo: Path, sha: str) -> Optional[int]:
    """Return the Unix timestamp of commit *sha*, or ``None``."""
    if not is_git_hash(sha):
        return None
    result = _run(["git", "show", "-s", "--format=%ct", sha], cwd=Path(repo))
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def diff_stats(
    path: Path,
    old_sha: Optional[str],
    new_sha: Optional[str],
    files: Optional[list[Path]] = None,
):
    """Return ``(hours, chars)`` between two commits for *path* or *files*.

    ``hours`` is the distance between the commit timestamps.  ``chars`` is
    the sum of the current character counts of the changed files.
    Returns ``None`` when the SHAs are not valid commits in the path's repo.
    """
    if not old_sha or not new_sha:
        return None
    repo, rel = _repo_rel(path)
    if repo is None:
        return None
    old_ts = commit_time(repo, old_sha)
    new_ts = commit_time(repo, new_sha)
    if old_ts is None or new_ts is None:
        return None

    rel_files = None
    if files is not None:
        rel_files = []
        for item in files:
            try:
                rel_files.append(Path(item).resolve().relative_to(repo).as_posix())
            except (OSError, ValueError):
                continue
        if not rel_files:
            return None

    hours = round(max(0.0, (new_ts - old_ts) / 3600.0), 2)
    chars = 0
    for rel_file in changed_paths(
        repo, old_sha, new_sha, rel_prefix=rel, rel_files=rel_files
    ):
        file_path = repo / rel_file
        if not file_path.is_file():
            continue
        if file_path.name in {
            ".memory_sources.md", ".memory_state.json", ".memory_queue.json",
            ".gitignore", ".DS_Store",
        }:
            continue
        try:
            chars += len(file_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            try:
                chars += file_path.stat().st_size
            except OSError:
                pass
    return hours, chars


def ensure_repo(memory_root: Path) -> Path:
    """Ensure *memory_root* is a git repository (local-only).

    Creates the directory, initializes git, writes a ``.gitignore`` for
    sidecar/OS files, and creates an initial baseline commit when the repo
    has no HEAD yet. Returns *memory_root*.
    """
    root = Path(memory_root)
    root.mkdir(parents=True, exist_ok=True)
    if not _git_available():
        return root

    if not (root / ".git").exists():
        _run(["git", "init", "--quiet"], cwd=root)
        for key, val in (("user.name", "agentone-memory"), ("user.email", "memory@agentone.local")):
            _run(["git", "config", key, val], cwd=root)

    gitignore = root / ".gitignore"
    desired = (
        ".memory_sources.md\n"
        ".memory_state.json\n"
        ".memory_queue.json\n"
        ".DS_Store\n"
        "__pycache__/\n"
        "*.pyc\n"
        "*.pyo\n"
    )
    if not gitignore.exists() or gitignore.read_text(encoding="utf-8") != desired:
        gitignore.write_text(desired, encoding="utf-8")

    if not _has_head(root):
        commit_all(root, message="baseline")
    return root


def _has_head(root: Path) -> bool:
    if not _git_available():
        return False
    return _run(["git", "rev-parse", "--verify", "HEAD"], cwd=root).returncode == 0


def head(memory_root: Path) -> str:
    """Return the current HEAD commit SHA (or ``""`` if unavailable)."""
    root = Path(memory_root)
    if not _git_available() or not (root / ".git").exists():
        return ""
    result = _run(["git", "rev-parse", "HEAD"], cwd=root)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def commit_all(memory_root: Path, message: str = "") -> str:
    """Stage all changes and commit if anything is dirty.

    Returns the (possibly unchanged) HEAD SHA. Safe to call when git is
    unavailable (returns ``""``).
    """
    root = Path(memory_root)
    if not _git_available() or not root.is_dir():
        return ""
    if not (root / ".git").exists():
        # Not a repo yet — initialize first.
        ensure_repo(root)

    _run(["git", "add", "-A"], cwd=root)

    has_head = _has_head(root)
    needs_commit = False
    if not has_head:
        needs_commit = True
    else:
        result = _run(["git", "diff-index", "--cached", "HEAD"], cwd=root)
        if result.stdout.strip():
            needs_commit = True

    if needs_commit:
        msg = message.strip() or f"sync {time.strftime('%Y-%m-%d %H:%M:%S')}"
        _run(["git", "commit", "--quiet", "-m", msg], cwd=root)

    return head(root)


def changed_paths(
    memory_root: Path,
    old_sha: Optional[str],
    new_sha: Optional[str],
    rel_prefix: str = "",
    rel_files: Optional[list[str]] = None,
) -> list[str]:
    """Return file paths changed between *old_sha* and *new_sha*.

    Paths are relative to *memory_root*. When *rel_prefix* is given, only
    paths starting with that prefix are returned. When *rel_files* is given,
    only those exact paths are returned. Returns ``[]`` when git is
    unavailable or the SHAs are equal/empty.
    """
    root = Path(memory_root)
    if not _git_available() or not old_sha or not new_sha or old_sha == new_sha:
        return []
    if not (root / ".git").exists():
        return []
    allowed = {
        item.strip().strip("/")
        for item in (rel_files or [])
        if item and item.strip().strip("/")
    }
    args = ["git", "diff", "--name-only", f"{old_sha}..{new_sha}"]
    if allowed:
        args.extend(["--", *sorted(allowed)])
    result = _run(args, cwd=root)
    if result.returncode != 0:
        return []
    out: list[str] = []
    prefix = rel_prefix.strip().strip("/")
    for line in result.stdout.splitlines():
        path = line.strip()
        if not path:
            continue
        if allowed and path not in allowed:
            continue
        if prefix and not (path == prefix or path.startswith(prefix + "/")):
            continue
        out.append(path)
    return out


def load_processed(layer_dir: Path) -> Optional[str]:
    """Return the last-processed commit SHA for *layer_dir*, or ``None``."""
    path = Path(layer_dir) / ".memory_state.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    sha = data.get("last_processed_commit")
    return str(sha).strip() or None if sha is not None else None


def save_processed(layer_dir: Path, sha: str) -> None:
    """Persist *sha* as the last-processed commit for *layer_dir*."""
    path = Path(layer_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / ".memory_state.json").write_text(
        json.dumps({"last_processed_commit": str(sha or "").strip()}, indent=2) + "\n",
        encoding="utf-8",
    )
