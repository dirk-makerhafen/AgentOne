"""SCRIPT tasks dispatch by interpreter on Windows (no shebang/exec bit)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from runtime.tasks import bound_task


class _FakeSelf:
    task_definition_version = SimpleNamespace(bound=False)
    session = SimpleNamespace(id=1, workspace=None, model=None)


@pytest.mark.parametrize(
    "suffix, expected_prefix",
    [
        (".py", [sys.executable]),
        (".ps1", ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]),
        (".cmd", ["cmd", "/c"]),
        (".bat", ["cmd", "/c"]),
    ],
)
def test_windows_script_commands(monkeypatch, tmp_path, suffix, expected_prefix):
    script = tmp_path / f"task{suffix}"
    script.write_text("print('ok')", encoding="utf-8")
    script.chmod(0o600)
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(bound_task.os, "name", "nt")
    monkeypatch.setattr(bound_task.subprocess, "run", fake_run)

    bound_task.BoundTask._call_script(_FakeSelf(), script, "arg")

    assert captured["cmd"] == [*expected_prefix, str(script), "arg"]
    # Windows has no executable bit; the source file must not be modified.
    assert script.stat().st_mode & 0o111 == 0


def test_posix_script_still_uses_executable_bit(monkeypatch, tmp_path):
    script = tmp_path / "task.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o600)
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(bound_task.os, "name", "posix")
    monkeypatch.setattr(bound_task.subprocess, "run", fake_run)

    bound_task.BoundTask._call_script(_FakeSelf(), script)

    assert captured["cmd"] == [str(script)]
    assert script.stat().st_mode & 0o111
