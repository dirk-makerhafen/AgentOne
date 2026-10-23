"""Tests for runtime.memory.git helpers (require git)."""

import json
import subprocess
from pathlib import Path

import pytest

from runtime.memory import git as memgit


def _git_ok() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


pytestmark = pytest.mark.skipif(not _git_ok(), reason="git not available")


def test_ensure_repo_creates_git(tmp_path):
    root = tmp_path / "memory"
    memgit.ensure_repo(root)
    assert (root / ".git").is_dir()
    assert (root / ".gitignore").is_file()
    assert memgit.head(root) != ""


def test_commit_all_noop_when_clean(tmp_path):
    root = tmp_path / "memory"
    memgit.ensure_repo(root)
    h1 = memgit.head(root)
    h2 = memgit.commit_all(root, message="noop")
    assert h1 == h2


def test_commit_all_commits_new_file(tmp_path):
    root = tmp_path / "memory"
    memgit.ensure_repo(root)
    h1 = memgit.head(root)
    (root / "a.md").write_text("hello", encoding="utf-8")
    h2 = memgit.commit_all(root, message="add a")
    assert h2 != h1
    assert memgit.head(root) == h2


def test_changed_paths(tmp_path):
    root = tmp_path / "memory"
    memgit.ensure_repo(root)
    (root / "x.md").write_text("v1", encoding="utf-8")
    h1 = memgit.commit_all(root, message="v1")
    (root / "x.md").write_text("v2", encoding="utf-8")
    (root / "y.md").write_text("new", encoding="utf-8")
    h2 = memgit.commit_all(root, message="v2")
    changed = memgit.changed_paths(root, h1, h2)
    assert "x.md" in changed
    assert "y.md" in changed


def test_changed_paths_prefix_filter(tmp_path):
    root = tmp_path / "memory"
    memgit.ensure_repo(root)
    (root / "agents").mkdir()
    (root / "agents" / "m.md").write_text("a", encoding="utf-8")
    h1 = memgit.commit_all(root, message="a")
    (root / "agents" / "m.md").write_text("b", encoding="utf-8")
    (root / "other.md").write_text("c", encoding="utf-8")
    h2 = memgit.commit_all(root, message="b")
    changed = memgit.changed_paths(root, h1, h2, rel_prefix="agents")
    assert "agents/m.md" in changed
    assert "other.md" not in changed


def test_path_commit_and_diff_stats(tmp_path):
    root = tmp_path / "memory"
    memgit.ensure_repo(root)
    (root / "a.md").write_text("one", encoding="utf-8")
    h1 = memgit.commit_all(root, message="one")
    (root / "a.md").write_text("three", encoding="utf-8")
    h2 = memgit.commit_all(root, message="two")

    assert memgit.path_commit(root / "a.md") == h2
    hours, chars = memgit.diff_stats(root / "a.md", h1, h2)
    assert hours == 0.0
    assert chars == len("three")
    assert memgit.diff_stats(root, "sha256:old", h2) is None


def test_diff_stats_can_limit_to_files(tmp_path):
    root = tmp_path / "memory"
    memgit.ensure_repo(root)
    layer = root / "child"
    (layer / "agents").mkdir(parents=True)
    (layer / "memory.md").write_text("old", encoding="utf-8")
    (layer / "agents" / "a.md").write_text("old", encoding="utf-8")
    h1 = memgit.commit_all(root, message="old")
    (layer / "memory.md").write_text("new memory", encoding="utf-8")
    (layer / "agents" / "a.md").write_text("new agent", encoding="utf-8")
    h2 = memgit.commit_all(root, message="new")

    _hours, chars = memgit.diff_stats(
        layer, h1, h2, files=[layer / "memory.md"]
    )
    assert chars == len("new memory")


def test_processed_sidecar(tmp_path):
    layer = tmp_path / "layer"
    layer.mkdir()
    assert memgit.load_processed(layer) is None
    memgit.save_processed(layer, "abc123")
    assert memgit.load_processed(layer) == "abc123"
    data = json.loads((layer / ".memory_state.json").read_text())
    assert data["last_processed_commit"] == "abc123"


def test_gitignore_ignores_sidecar(tmp_path):
    root = tmp_path / "memory"
    memgit.ensure_repo(root)
    memgit.save_processed(root, "deadbeef")
    # sidecar should not show as untracked/dirty
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True
    )
    assert ".memory_state.json" not in status.stdout
