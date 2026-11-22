"""Restart detection and the detached restart helper."""

from __future__ import annotations

import json

from launcher import restart, restart_helper


def test_configured_restart_command_wins(settings):
    settings.AGENTONE_RESTART_COMMAND = ["sudo", "-n", "supervisorctl", "restart", "agentone-server"]

    assert restart.detect_restart_command() == settings.AGENTONE_RESTART_COMMAND


def test_no_restart_command_when_nothing_detected(monkeypatch, settings):
    settings.AGENTONE_RESTART_COMMAND = []
    settings.AGENTONE_SERVICE_MANAGER = "systemd"
    monkeypatch.setattr(restart.shutil, "which", lambda name: None)

    assert restart.detect_restart_command() is None


def test_request_restart_spawns_detached_helper(monkeypatch, tmp_path, settings):
    settings.LOG_DIR = str(tmp_path)
    spawned = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            spawned["args"] = args
            spawned["kwargs"] = kwargs

    monkeypatch.setattr(restart.subprocess, "Popen", FakePopen)

    assert restart.request_restart(["supervisorctl", "restart", "agentone-server"]) is True
    assert "-m" in spawned["args"]
    assert "launcher.restart_helper" in spawned["args"]
    assert spawned["kwargs"]["start_new_session"] is True
    assert spawned["kwargs"]["cwd"] == str(settings.BASE_DIR)


def test_restart_helper_runs_json_command(monkeypatch, tmp_path):
    log_file = tmp_path / "restart.log"
    recorded = {}

    class FakeResult:
        returncode = 0
        stderr = ""
        stdout = "OK"

    def fake_run(command, **kwargs):
        recorded["command"] = command
        return FakeResult()

    monkeypatch.setattr(restart_helper.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(restart_helper.subprocess, "run", fake_run)

    code = restart_helper.main([
        "--delay", "3",
        "--command", json.dumps(["supervisorctl", "restart", "agentone-server"]),
        "--log-file", str(log_file),
    ])

    assert code == 0
    assert recorded["command"] == ["supervisorctl", "restart", "agentone-server"]
    assert "restart ok" in log_file.read_text(encoding="utf-8")


def test_restart_helper_rejects_bad_command():
    assert restart_helper.main(["--command", '"not-a-list"']) == 2
