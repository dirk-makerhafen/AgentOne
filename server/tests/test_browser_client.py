"""Windows-safe browser daemon startup and cross-platform file locks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from runtime import file_lock
from runtime.browser import client


class _FakePsutil:
    @staticmethod
    def pid_exists(pid):
        return pid == 4242


def test_pid_alive_never_signals_on_windows(monkeypatch):
    monkeypatch.setattr(client.sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "psutil", _FakePsutil)

    def forbidden(*args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("os.kill must not be called on Windows")

    monkeypatch.setattr(os, "kill", forbidden)

    assert client._pid_alive(4242) is True
    assert client._pid_alive(999) is False
    assert client._pid_alive("4242") is False


def test_pid_alive_uses_psutil_on_posix(monkeypatch):
    monkeypatch.setattr(client.sys, "platform", "darwin")
    monkeypatch.setitem(sys.modules, "psutil", _FakePsutil)
    monkeypatch.setattr(os, "kill", lambda *a, **k: pytest.fail("signal probe used"))

    assert client._pid_alive(4242) is True


def test_spawn_daemon_detaches_on_windows(monkeypatch, tmp_path):
    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    monkeypatch.setattr(client.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(client.sys, "platform", "win32")
    monkeypatch.setattr(client.subprocess, "DETACHED_PROCESS", 0x8, raising=False)
    monkeypatch.setattr(client.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    monkeypatch.setattr(client.subprocess, "CREATE_NO_WINDOW", 0x8000000, raising=False)
    monkeypatch.setattr(client.paths, "browser_base", lambda: tmp_path)
    monkeypatch.setattr(client.paths, "ensure_private_dir", lambda _path: None)

    client._spawn_daemon()

    assert captured["args"] == [sys.executable, "-m", "runtime.browser.daemon"]
    assert "start_new_session" not in captured["kwargs"]
    assert captured["kwargs"]["creationflags"] == 0x8 | 0x200 | 0x8000000
    assert (tmp_path / "daemon.log").exists()


def test_spawn_daemon_uses_start_new_session_on_posix(monkeypatch, tmp_path):
    captured = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            captured["kwargs"] = kwargs

    monkeypatch.setattr(client.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(client.sys, "platform", "darwin")
    monkeypatch.setattr(client.paths, "browser_base", lambda: tmp_path)
    monkeypatch.setattr(client.paths, "ensure_private_dir", lambda _path: None)

    client._spawn_daemon()

    assert captured["kwargs"]["start_new_session"] is True
    assert "creationflags" not in captured["kwargs"]


def test_ensure_daemon_uses_the_cross_platform_lock(monkeypatch, tmp_path: Path):
    lock_path = tmp_path / "start.lock"
    health_calls = []

    def healthy(_port, timeout=3.0):
        health_calls.append(timeout)
        return len(health_calls) > 1  # first probe fails, re-check under lock wins

    monkeypatch.setattr(client.paths, "start_lock_path", lambda: lock_path)
    monkeypatch.setattr(client.paths, "browser_base", lambda: tmp_path)
    monkeypatch.setattr(client, "_read_state", lambda: {"pid": 4242, "port": 8765})
    monkeypatch.setattr(client, "_pid_alive", lambda _pid: True)
    monkeypatch.setattr(client, "_healthy", healthy)

    assert client.ensure_daemon() == 8765
    assert lock_path.exists()


def test_file_lock_is_exclusive_and_released(monkeypatch, tmp_path):
    path = tmp_path / "test.lock"
    with file_lock.file_lock(path, timeout=0.1):
        assert path.exists()
        with pytest.raises(file_lock.FileLockTimeout):
            with file_lock.file_lock(path, timeout=0):
                pass  # pragma: no cover - must not be reached

    with file_lock.file_lock(path, timeout=0.1):
        pass
