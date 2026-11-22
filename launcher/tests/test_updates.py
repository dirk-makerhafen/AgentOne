"""Tests for the shared update pipeline (CLI and UI use the same code)."""

from __future__ import annotations

from contextlib import nullcontext

import pytest

from launcher import updates
from launcher.updates import UpdateError


def _patch_pipeline(monkeypatch, repo, *, behind="2", dirty="", restart_command=None):
    calls = []

    def fake_git_capture(args, root, description):
        calls.append(("git", tuple(args), description))
        if args[0] == "status":
            return dirty
        if args[0] == "rev-list":
            return behind
        return ""

    monkeypatch.setattr(updates, "_git_capture", fake_git_capture)
    monkeypatch.setattr(updates, "update_lock", nullcontext)
    monkeypatch.setattr(
        updates, "_run_streaming",
        lambda command, root, description, log, **kwargs: calls.append(("run", tuple(command), description)),
    )
    monkeypatch.setattr(
        updates, "_django_command",
        lambda name, log, **kwargs: calls.append(("django", name, kwargs)),
    )
    monkeypatch.setattr(
        "registry.management.commands.reload_all.run_reload_all",
        lambda folder: {"status": "success", "summary": "Manifests reloaded.", "errors": []},
    )
    monkeypatch.setattr("launcher.restart.detect_restart_command", lambda root=None: restart_command)
    monkeypatch.setattr(
        "launcher.restart.request_restart",
        lambda command, root=None, delay=3: calls.append(("restart", tuple(command), delay)) or True,
    )

    versions = iter([
        {"version": "0.1.0+aaaaaaa", "commit": "aaaaaaa111", "short_commit": "aaaaaaa", "branch": "main"},
        {"version": "0.1.0+bbbbbbb", "commit": "bbbbbbb222", "short_commit": "bbbbbbb", "branch": "main"},
    ])
    monkeypatch.setattr("runtime.version.get_version_info", lambda *a, **kw: next(versions))
    monkeypatch.setattr("runtime.version.clear_version_cache", lambda: None)
    return calls


@pytest.fixture
def repo(tmp_path, settings):
    (tmp_path / ".git").mkdir()
    (tmp_path / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("Django\n", encoding="utf-8")
    settings.BASE_DIR = str(tmp_path)
    settings.DEBUG = False
    return tmp_path


def test_full_update_runs_every_step(repo, monkeypatch):
    calls = _patch_pipeline(monkeypatch, repo)
    logs = []

    result = updates.run_update(log=lambda message, level="info": logs.append((message, level)))

    kinds = [call[0] for call in calls]
    assert "django" in kinds and "run" in kinds and "restart" not in kinds
    assert any(call[0] == "django" and call[1] == "migrate" for call in calls)
    assert any(call[0] == "django" and call[1] == "collectstatic" for call in calls)
    assert result["status"] == "updated"
    assert result["before"] == "0.1.0+aaaaaaa"
    assert result["after"] == "0.1.0+bbbbbbb"
    assert any("Python dependencies" in message for message, _ in logs)
    assert any(level == "success" for _, level in logs)


def test_update_schedules_restart_when_manager_detected(repo, monkeypatch):
    command = ["supervisorctl", "restart", "agentone-server"]
    calls = _patch_pipeline(monkeypatch, repo, restart_command=command)

    result = updates.run_update()

    assert result["restart"] == "scheduled"
    assert ("restart", tuple(command), 3) in calls


def test_update_can_skip_restart(repo, monkeypatch):
    command = ["systemctl", "restart", "agentone_server.service"]
    calls = _patch_pipeline(monkeypatch, repo, restart_command=command)

    result = updates.run_update(restart=False)

    assert result["restart"] == "skipped"
    assert not any(call[0] == "restart" for call in calls)


def test_up_to_date_short_circuits(repo, monkeypatch):
    calls = _patch_pipeline(monkeypatch, repo, behind="0")

    result = updates.run_update()

    assert result["status"] == "up_to_date"
    assert not any(call[0] in ("django", "run", "restart") for call in calls)


def test_force_runs_pipeline_when_up_to_date(repo, monkeypatch):
    calls = _patch_pipeline(monkeypatch, repo, behind="0")

    result = updates.run_update(force=True)

    assert result["status"] == "updated"
    assert any(call[0] == "django" and call[1] == "migrate" for call in calls)


def test_dirty_worktree_is_refused(repo, monkeypatch):
    calls = _patch_pipeline(monkeypatch, repo, dirty=" M local_edit.py")

    with pytest.raises(UpdateError, match="uncommitted changes"):
        updates.run_update()

    assert not any(call[1] and call[1][0] == "fetch" for call in calls if call[0] == "git")


def test_dirty_worktree_allowed_explicitly(repo, monkeypatch):
    _patch_pipeline(monkeypatch, repo, dirty=" M local_edit.py")

    result = updates.run_update(allow_dirty=True)

    assert result["status"] == "updated"


def test_migration_failure_aborts_before_collectstatic(repo, monkeypatch):
    calls = _patch_pipeline(monkeypatch, repo)

    def failing_command(name, log, **kwargs):
        calls.append(("django", name, kwargs))
        if name == "migrate":
            raise RuntimeError("bad migration")

    monkeypatch.setattr(updates, "_django_command", failing_command)

    with pytest.raises(UpdateError, match="Migration failed"):
        updates.run_update()

    assert not any(call[0] == "django" and call[1] == "collectstatic" for call in calls)
