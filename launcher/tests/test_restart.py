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


def test_windows_service_is_detected(monkeypatch, settings):
    settings.AGENTONE_RESTART_COMMAND = []
    settings.AGENTONE_SERVICE_MANAGER = "auto"
    settings.AGENTONE_SERVICE_NAME = ""
    monkeypatch.setattr(restart.sys, "platform", "win32")
    monkeypatch.setattr(
        restart.shutil, "which",
        lambda name: "/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" if name == "powershell" else None,
    )
    monkeypatch.setattr(restart, "_windows_service_exists", lambda name: name == "agentone_server")

    command = restart.detect_restart_command()

    assert command[0].endswith("powershell.exe")
    assert command[1:-2] == ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass"]
    assert "Stop-Service" in command[-1]
    assert "Start-Service" in command[-1]
    assert "agentone_server" in command[-1]


def test_windows_service_name_override(monkeypatch, settings):
    settings.AGENTONE_RESTART_COMMAND = []
    settings.AGENTONE_SERVICE_MANAGER = "windows"
    settings.AGENTONE_SERVICE_NAME = "MyAgent"
    monkeypatch.setattr(restart.sys, "platform", "win32")
    monkeypatch.setattr(
        restart.shutil, "which",
        lambda name: "/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" if name == "powershell" else None,
    )
    monkeypatch.setattr(restart, "_windows_service_exists", lambda name: name == "MyAgent")

    assert "MyAgent" in restart.detect_restart_command()[-1]


def test_windows_manager_is_ignored_on_other_platforms(monkeypatch, settings):
    settings.AGENTONE_RESTART_COMMAND = []
    settings.AGENTONE_SERVICE_MANAGER = "windows"
    monkeypatch.setattr(restart.sys, "platform", "darwin")
    monkeypatch.setattr(restart.shutil, "which", lambda name: None)

    assert restart.detect_restart_command() is None


def test_windows_service_exists_checks_sc_output(monkeypatch):
    class Result:
        returncode = 0
        stdout = ""

    result = Result()
    monkeypatch.setattr(restart.subprocess, "run", lambda *args, **kwargs: result)

    result.stdout = "SERVICE_NAME: agentone_server\nSTATE : 4 RUNNING"
    assert restart._windows_service_exists("agentone_server") is True

    result.stdout = "The specified service does not exist as an installed service."
    assert restart._windows_service_exists("agentone_server") is False


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


def test_request_restart_windows_uses_creationflags(monkeypatch, tmp_path, settings):
    settings.LOG_DIR = str(tmp_path)
    spawned = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            spawned["args"] = args
            spawned["kwargs"] = kwargs

    monkeypatch.setattr(restart.sys, "platform", "win32")
    monkeypatch.setattr(restart.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(restart.subprocess, "DETACHED_PROCESS", 0x8, raising=False)
    monkeypatch.setattr(restart.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    monkeypatch.setattr(restart.subprocess, "CREATE_NO_WINDOW", 0x8000000, raising=False)

    assert restart.request_restart(["powershell", "-Command", "x"]) is True
    assert "start_new_session" not in spawned["kwargs"]
    assert spawned["kwargs"]["creationflags"] == 0x8 | 0x200 | 0x8000000
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
