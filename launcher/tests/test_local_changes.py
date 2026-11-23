"""Tests for the staff-only local-change resolution helpers."""

from __future__ import annotations

import pytest

from launcher import local_changes
from launcher.updates import UpdateError


def _fake_git(monkeypatch, *, dirty="", conflicts=(), pop_fails=False):
    calls = []

    def fake_git(args, root, description):
        calls.append(tuple(args))
        if args[0] == "status":
            return dirty
        if args[:2] == ["rev-parse", "--verify"]:
            return "abc123def456"
        if args[:2] == ["stash", "pop"] and pop_fails:
            raise UpdateError("CONFLICT (content): Merge conflict")
        if args[0] == "diff" and "--diff-filter=U" in args:
            return "\n".join(conflicts)
        return ""

    monkeypatch.setattr(local_changes, "_git_capture", fake_git)
    monkeypatch.setattr(local_changes, "clear_version_cache", lambda: None)
    return calls


def test_undo_stashes_changes_instead_of_deleting(monkeypatch, tmp_path):
    calls = _fake_git(monkeypatch, dirty=" M launcher/updates.py\n?? scratch.txt\n")

    result = local_changes.undo_local_changes(path=tmp_path)

    assert result["status"] == "undone"
    assert result["stash_ref"] == "abc123def456"
    assert result["paths"] == ["launcher/updates.py", "scratch.txt"]
    assert ("stash", "push", "--include-untracked", "--message", calls[-2][-1]) in calls
    assert not any(call[:2] == ("stash", "drop") for call in calls)


def test_undo_on_clean_tree_is_a_noop(monkeypatch, tmp_path):
    _fake_git(monkeypatch)

    result = local_changes.undo_local_changes(path=tmp_path)

    assert result == {"status": "already_clean"}


def test_merge_stashes_updates_and_reapplies(monkeypatch, tmp_path):
    calls = _fake_git(monkeypatch, dirty=" M launcher/updates.py\n")
    monkeypatch.setattr(
        local_changes, "run_update",
        lambda **kwargs: {"status": "up_to_date", "restart": "skipped"},
    )

    result = local_changes.merge_local_changes(path=tmp_path)

    assert result["status"] == "merged"
    assert ("stash", "push", "--include-untracked", "--message", calls[1][-1]) in calls
    assert ("stash", "pop", "abc123def456") in calls


def test_merge_resolves_conflicts_for_local_preference(monkeypatch, tmp_path):
    calls = _fake_git(monkeypatch, dirty=" M launcher/updates.py\n", conflicts=["launcher/updates.py"], pop_fails=True)
    monkeypatch.setattr(
        local_changes, "run_update",
        lambda **kwargs: {"status": "updated", "restart": "skipped"},
    )

    result = local_changes.merge_local_changes(path=tmp_path, preference="local")

    assert result["status"] == "merged"
    assert result["conflicts_resolved"] == ["launcher/updates.py"]
    assert ("checkout", "--theirs", "--", "launcher/updates.py") in calls
    assert ("stash", "drop", "abc123def456") in calls


def test_merge_resolves_conflicts_for_remote_preference(monkeypatch, tmp_path):
    calls = _fake_git(monkeypatch, dirty=" M launcher/updates.py\n", conflicts=["launcher/updates.py"], pop_fails=True)
    monkeypatch.setattr(
        local_changes, "run_update",
        lambda **kwargs: {"status": "updated", "restart": "skipped"},
    )

    result = local_changes.merge_local_changes(path=tmp_path, preference="remote")

    assert result["status"] == "merged"
    assert ("checkout", "--ours", "--", "launcher/updates.py") in calls


def test_merge_returns_conflicts_for_llm_session(monkeypatch, tmp_path):
    _fake_git(monkeypatch, dirty=" M launcher/updates.py\n", conflicts=["launcher/updates.py"], pop_fails=True)
    monkeypatch.setattr(
        local_changes, "run_update",
        lambda **kwargs: {"status": "updated", "restart": "skipped"},
    )

    result = local_changes.merge_local_changes(path=tmp_path)

    assert result["status"] == "conflict"
    assert result["conflicts"] == ["launcher/updates.py"]
    assert result["stash_ref"] == "abc123def456"


def test_failed_update_restores_the_stash(monkeypatch, tmp_path):
    calls = _fake_git(monkeypatch, dirty=" M launcher/updates.py\n")

    def fail(**kwargs):
        raise UpdateError("pull failed")

    monkeypatch.setattr(local_changes, "run_update", fail)

    with pytest.raises(UpdateError, match="still in stash"):
        local_changes.merge_local_changes(path=tmp_path)

    assert ("stash", "pop", "abc123def456") in calls


@pytest.mark.django_db
def test_merge_task_opens_a_chat_when_conflicts_remain(monkeypatch):
    from launcher import tasks

    monkeypatch.setattr(tasks, "append_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks, "release_queue", lambda: None)
    finished = {}
    monkeypatch.setattr(
        tasks, "finish_run",
        lambda run_id, status, **kwargs: finished.update(id=run_id, status=status, result=kwargs.get("result")),
    )
    monkeypatch.setattr(
        local_changes, "merge_local_changes",
        lambda **kwargs: {
            "status": "conflict", "conflicts": ["launcher/updates.py"],
            "paths": ["launcher/updates.py"], "stash_ref": "abc123", "preference": "",
        },
    )
    started = {}

    def fake_session(**kwargs):
        started.update(kwargs)
        return 77

    monkeypatch.setattr("webui.features.settings.sessions.start_conflict_session", fake_session)

    tasks.resolve_local_changes("run42", "merge")

    assert finished["status"] == "needs_attention"
    assert finished["result"]["session_id"] == 77
    assert started["conflicts"] == ["launcher/updates.py"]


@pytest.mark.django_db
def test_undo_task_finishes_successfully(monkeypatch):
    from launcher import tasks

    monkeypatch.setattr(tasks, "append_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(tasks, "release_queue", lambda: None)
    finished = {}
    monkeypatch.setattr(
        tasks, "finish_run",
        lambda run_id, status, **kwargs: finished.update(id=run_id, status=status, result=kwargs.get("result")),
    )
    monkeypatch.setattr(local_changes, "undo_local_changes", lambda **kwargs: {"status": "undone"})

    tasks.resolve_local_changes("run43", "undo")

    assert finished == {"id": "run43", "status": "success", "result": {"status": "undone"}}
