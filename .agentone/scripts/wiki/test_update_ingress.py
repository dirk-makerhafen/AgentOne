from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, "/Users/Dirk/AgentOne/.agentone/agents/wiki/scripts")

from update_ingress import (  # noqa: E402
    _matches_any,
    _parse_queue_line,
    _tag_set,
    refresh_ingress,
)

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def _repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", cwd=path)
    _git("config", "user.email", "test@example.org", cwd=path)
    _git("config", "user.name", "Test", cwd=path)
    return path


def _commit_all(repo: Path, message: str = "checkpoint") -> None:
    _git("add", "-A", cwd=repo)
    _git("commit", "-qm", message, cwd=repo)


def _write(repo: Path, rel: str, text: str) -> Path:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


SUMMARY = "---\ntype: summary\ntags: [workshop]\n---\n\n# {title}\n"
AD = "---\ntype: summary\ntags: [werbung]\n---\n\n# {title}\n"

INGRESS = """\
---
type: ingress
sources: ["timeline/**/*.md"]
exclude: ["timeline/**/index.md"]
exclude_tags: [werbung]
---
"""


def test_matches_any_zero_dir_wildcard():
    assert _matches_any("timeline/a.md", ["timeline/**/*.md"])
    assert _matches_any("timeline/2022/10/x.md", ["timeline/**/*.md"])
    assert not _matches_any("entities/X.md", ["timeline/**/*.md"])
    assert _matches_any("timeline/2022/10/index.md", ["timeline/**/index.md"])
    assert not _matches_any("timeline/2022/10/x.md", ["timeline/**/index.md"])


def test_missing_sources_is_error(tmp_path):
    _write(tmp_path, "cal/ingress.md", "---\ntype: ingress\n---\n")
    ok, info = refresh_ingress(tmp_path, "cal/ingress.md")
    assert not ok and "sources" in info["message"]


def test_missing_file_is_error(tmp_path):
    ok, info = refresh_ingress(tmp_path, "cal/ingress.md")
    assert not ok and "not found" in info["message"]


@needs_git
def test_first_run_full_expansion(tmp_path):
    repo = _repo(tmp_path / "vault")
    _write(repo, "cal/ingress.md", INGRESS)
    _write(repo, "timeline/2022/10/01/workshop.md", SUMMARY.format(title="Workshop"))
    _write(repo, "timeline/2022/10/01/ad.md", AD.format(title="Ad"))
    _write(repo, "timeline/2022/10/index.md", "---\ntype: index\n---\n")
    _commit_all(repo)
    ok, info = refresh_ingress(repo, "cal/ingress.md")
    assert ok, info
    # Workshop queued; ad dropped by exclude_tags; index dropped by exclude;
    # ingress file itself never a queue item. First run always full-scans.
    assert info["queued"] == 1 and info["full_scan"] and info["fresh"] == 1
    # Quiet rerun: pure diff, nothing fresh, unfinished line persists.
    ok, rerun = refresh_ingress(repo, "cal/ingress.md")
    assert ok and rerun["queued"] == 1 and rerun["fresh"] == 0 and not rerun["full_scan"]
    body = (repo / "cal/ingress.md").read_text(encoding="utf-8")
    parsed = [_parse_queue_line(l) for l in body.split("---", 2)[-1].splitlines()]
    rels = [rel for rel, _done, _del, _meta in parsed if rel]
    assert rels == ["timeline/2022/10/01/workshop.md"]
    assert all(not done for _r, done, _d, _m in parsed if _r)
    first = next(l for l in body.split("---", 2)[-1].splitlines() if l.strip())
    assert first.startswith("- [ ] timeline/2022/10/01/workshop.md <!-- queued ")
    assert "last_checked_at:" in body and "updated:" in body
    # No memory files: the ingress file is the only state.
    assert list((repo / "cal").glob(".*")) == []


@needs_git
def test_incremental_merge_and_rechange(tmp_path):
    repo = _repo(tmp_path / "vault")
    _write(repo, "cal/ingress.md", INGRESS)
    _write(repo, "timeline/a.md", SUMMARY.format(title="A"))
    _write(repo, "timeline/b.md", SUMMARY.format(title="B"))
    _commit_all(repo)
    ok, info = refresh_ingress(repo, "cal/ingress.md")
    assert ok and info["queued"] == 2

    # Consumer finishes `a` (deletes the line). Quiet rerun: the window is
    # empty, `a` stays gone with no memory files, `b` persists unfinished.
    queue = repo / "cal/ingress.md"
    queue.write_text("\n".join(l for l in queue.read_text(encoding="utf-8").splitlines()
                               if "timeline/a.md" not in l) + "\n", encoding="utf-8")
    ok, info = refresh_ingress(repo, "cal/ingress.md")
    assert ok, info
    assert info["queued"] == 1 and info["fresh"] == 0 and not info["full_scan"]
    assert "timeline/a.md" not in queue.read_text(encoding="utf-8")

    # New commit `c` arrives through the window; uncommitted `d` does not
    # (committed state only) until it too is committed.
    _write(repo, "timeline/c.md", SUMMARY.format(title="C"))
    _write(repo, "timeline/d.md", SUMMARY.format(title="D"))
    _git("add", "timeline/c.md", "cal/ingress.md", cwd=repo)
    _git("commit", "-qm", "c", cwd=repo)
    ok, info = refresh_ingress(repo, "cal/ingress.md")
    assert ok and info["queued"] == 2  # b + c, no a, no d
    assert "timeline/d.md" not in queue.read_text(encoding="utf-8")
    _commit_all(repo, "d")
    ok, info = refresh_ingress(repo, "cal/ingress.md")
    assert ok and info["queued"] == 3

    # `b` finished, then changed AGAIN -> returns through a newer window.
    queue.write_text("\n".join(l for l in queue.read_text(encoding="utf-8").splitlines()
                               if "timeline/b.md" not in l) + "\n", encoding="utf-8")
    _write(repo, "timeline/b.md", SUMMARY.format(title="B v2"))
    _commit_all(repo, "b2")
    ok, info = refresh_ingress(repo, "cal/ingress.md")
    assert ok and "timeline/b.md" in queue.read_text(encoding="utf-8")


@needs_git
def test_removed_file_marked_deleted(tmp_path):
    repo = _repo(tmp_path / "vault")
    _write(repo, "cal/ingress.md", INGRESS)
    _write(repo, "timeline/gone.md", SUMMARY.format(title="Gone"))
    assert refresh_ingress(repo, "cal/ingress.md")[0]
    _commit_all(repo)
    _git("rm", "-q", "timeline/gone.md", cwd=repo)
    _git("commit", "-qm", "remove", cwd=repo)
    ok, info = refresh_ingress(repo, "cal/ingress.md")
    assert ok, info
    assert info["marked_deleted"] == 1
    assert "timeline/gone.md (deleted)" in (repo / "cal/ingress.md").read_text(encoding="utf-8")

def test_no_git_full_scan(tmp_path):
    _write(tmp_path, "cal/ingress.md", INGRESS)
    _write(tmp_path, "timeline/x.md", SUMMARY.format(title="X"))
    ok, info = refresh_ingress(tmp_path, "cal/ingress.md")
    assert ok, info
    assert info["full_scan"] and info["queued"] == 1
    assert "unknown (no git" in (tmp_path / "cal/ingress.md").read_text(encoding="utf-8")


def test_parse_queue_line_format(tmp_path):
    assert _parse_queue_line("") == (None, False, False, {})
    assert _parse_queue_line("timeline/a.md") == ("timeline/a.md", False, False, {})
    assert _parse_queue_line("timeline/a.md (deleted)") == ("timeline/a.md", False, True, {})
    rel, done, deleted, meta = _parse_queue_line(
        "- [ ] timeline/a.md <!-- queued 2026-10-11 @ 3e9b405d -->")
    assert (rel, done, deleted) == ("timeline/a.md", False, False)
    assert meta == {"queued": "2026-10-11", "head": "3e9b405d"}
    rel, done, deleted, meta = _parse_queue_line(
        "- [x] timeline/a.md <!-- queued 2026-10-09 @ b64b6a76 | done 2026-10-11 -->")
    assert (rel, done, deleted) == ("timeline/a.md", True, False)
    assert meta == {"queued": "2026-10-09", "head": "b64b6a76", "done": "2026-10-11"}
    rel, _done, _del, meta = _parse_queue_line("- [ ] timeline/a.md <!-- queued 2026-10-11 | active 1720000000 -->")
    assert meta.get("active") == 1720000000


@needs_git
def test_done_history_compaction(tmp_path):
    import datetime
    today = datetime.date.today()
    old = (today - datetime.timedelta(days=200)).isoformat()
    new = (today - datetime.timedelta(days=2)).isoformat()
    repo = _repo(tmp_path / "vault")
    old_done = f"- [x] timeline/old.md <!-- queued {old} @ aaaaaaaa | done {old} -->"
    new_done = f"- [x] timeline/new.md <!-- queued {new} @ bbbbbbbb | done {new} -->"
    _write(repo, "cal/ingress.md", INGRESS + old_done + "\n" + new_done + "\n")
    _write(repo, "timeline/live.md", SUMMARY.format(title="Live"))
    _commit_all(repo)
    ok, info = refresh_ingress(repo, "cal/ingress.md")
    assert ok, info
    assert info["done_kept"] == 1
    body = (repo / "cal/ingress.md").read_text(encoding="utf-8")
    assert "timeline/old.md" not in body and "timeline/new.md" in body


def test_tag_set_helper():
    assert _tag_set({"include_tags": ["Workshop", "buchung"]}, "include_tags") == {"workshop", "buchung"}
    # Scalar form constrains exactly like list form — never silently "match all".
    assert _tag_set({"include_tags": "Workshop"}, "include_tags") == {"workshop"}
    assert _tag_set({"exclude_tags": "werbung"}, "exclude_tags") == {"werbung"}
    assert _tag_set({}, "include_tags") == set()
    assert _tag_set({"include_tags": None}, "include_tags") == set()


@needs_git
def test_include_and_exclude_tags_end_to_end(tmp_path):
    repo = _repo(tmp_path / "vault")
    _write(repo, "cal/ingress.md", INGRESS.replace(
        "exclude_tags: [werbung]",
        "include_tags: [workshop, buchung]\nexclude_tags: [werbung]"))
    _write(repo, "timeline/keep.md", SUMMARY.format(title="Keep"))
    _write(repo, "timeline/booked.md", "---\ntype: summary\ntags: [buchung]\n---\n\n# B\n")
    _write(repo, "timeline/other.md", "---\ntype: summary\ntags: [rechnung]\n---\n\n# R\n")
    _write(repo, "timeline/spam.md", "---\ntype: summary\ntags: [workshop, werbung]\n---\n\n# S\n")
    _write(repo, "timeline/notags.md", "---\ntype: summary\n---\n\n# No tags at all\n")
    _write(repo, "timeline/plain.md", "no frontmatter here\n")
    _commit_all(repo)
    ok, info = refresh_ingress(repo, "cal/ingress.md")
    assert ok, info
    assert info["queued"] == 2
    queue = (repo / "cal/ingress.md").read_text(encoding="utf-8").split("---", 2)[-1]
    assert "timeline/keep.md" in queue and "timeline/booked.md" in queue
    assert "other.md" not in queue and "spam.md" not in queue
    assert "notags.md" not in queue and "plain.md" not in queue
    # Tag selection survives the frontmatter rewrite round-trip.
    re_fm = (repo / "cal/ingress.md").read_text(encoding="utf-8")
    assert "include_tags: [workshop, buchung]" in re_fm
    ok, rerun = refresh_ingress(repo, "cal/ingress.md")
    assert ok and rerun["queued"] == 2 and rerun["fresh"] == 0


@needs_git
def test_gone_file_queued_despite_include_tags(tmp_path):
    repo = _repo(tmp_path / "vault")
    _write(repo, "cal/ingress.md", INGRESS.replace(
        "exclude_tags: [werbung]", "include_tags: [workshop]"))
    _write(repo, "timeline/gone.md", SUMMARY.format(title="Gone"))
    assert refresh_ingress(repo, "cal/ingress.md")[0]
    _commit_all(repo)
    _git("rm", "-q", "timeline/gone.md", cwd=repo)
    _git("commit", "-qm", "remove", cwd=repo)
    ok, info = refresh_ingress(repo, "cal/ingress.md")
    assert ok and info["marked_deleted"] == 1
    assert "timeline/gone.md (deleted)" in (repo / "cal/ingress.md").read_text(encoding="utf-8")
