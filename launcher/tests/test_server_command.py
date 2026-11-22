"""The ``manage.py server update`` CLI front-end."""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command


def test_update_check_only_never_runs_pipeline(monkeypatch):
    from runtime import version

    monkeypatch.setattr(version, "update_status", lambda refresh=False: {
        "version": "0.1.0+abc1234",
        "short_commit": "abc1234",
        "branch": "main",
        "dirty": False,
        "remote_short_commit": "def5678",
        "available": True,
    })
    called = []
    monkeypatch.setattr("launcher.updates.run_update", lambda **kwargs: called.append(kwargs) or {})

    out = StringIO()
    call_command("server", "update", check=True, stdout=out)

    assert "0.1.0+abc1234" in out.getvalue()
    assert "available" in out.getvalue()
    assert called == []


def test_update_passes_cli_flags_to_pipeline(monkeypatch):
    from runtime import version

    monkeypatch.setattr(version, "update_status", lambda refresh=False: {
        "version": "0.1.0+abc1234", "short_commit": "abc1234", "branch": "main",
        "dirty": False, "remote_short_commit": "", "available": False,
    })
    monkeypatch.setattr(version, "get_version_info", lambda refresh=False: {"version": "0.1.0+def5678"})
    captured = {}

    def fake_run_update(**kwargs):
        captured.update(kwargs)
        return {
            "status": "updated", "before": "0.1.0+abc", "after": "0.1.0+def",
            "restart": "scheduled" if kwargs.get("restart") else "skipped",
        }

    monkeypatch.setattr("launcher.updates.run_update", fake_run_update)

    out = StringIO()
    call_command(
        "server", "update",
        allow_dirty=True, force=True, no_restart=True, branch="release",
        stdout=out,
    )

    assert captured["allow_dirty"] is True
    assert captured["force"] is True
    assert captured["restart"] is False
    assert captured["branch"] == "release"
    assert "will restart" not in out.getvalue()
