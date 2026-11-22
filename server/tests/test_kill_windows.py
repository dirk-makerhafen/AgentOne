"""The kill tool must not build signal maps with Windows-missing constants."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "agentone_kill_tool", ROOT / ".agentone" / "scripts" / "execution" / "kill.py"
)
kill_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kill_tool)


def test_sigkill_falls_back_to_terminate_process(monkeypatch):
    # A Windows-like signal module has neither SIGKILL nor SIGHUP.
    monkeypatch.setattr(kill_tool, "signal", SimpleNamespace(SIGTERM=15, SIGINT=2))

    killed = []

    class FakeProcess:
        def __init__(self, pid):
            self.pid = pid

        def kill(self):
            killed.append(self.pid)

        def send_signal(self, sig):  # pragma: no cover - failure path
            raise AssertionError("send_signal should not be used for SIGKILL")

    monkeypatch.setattr(kill_tool.psutil, "Process", FakeProcess)

    ok, result = kill_tool.kill(pid=123, signal_name="SIGKILL")

    assert ok is True
    assert result["killed"] == [123]
    assert result["signal"] == "SIGKILL"


def test_unsupported_signal_is_a_clean_error(monkeypatch):
    monkeypatch.setattr(kill_tool, "signal", SimpleNamespace(SIGTERM=15, SIGINT=2))

    class FakeProcess:
        def __init__(self, pid):
            self.pid = pid

        def kill(self):  # pragma: no cover - failure path
            raise AssertionError("kill should not be used for SIGHUP")

        def send_signal(self, sig):  # pragma: no cover - failure path
            raise AssertionError("send_signal should not be used for SIGHUP")

    monkeypatch.setattr(kill_tool.psutil, "Process", FakeProcess)

    ok, result = kill_tool.kill(pid=123, signal_name="SIGHUP")

    assert ok is False
    assert "not supported" in result["message"]
