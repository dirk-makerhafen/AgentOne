"""The checkout's venv must win no matter how manage.py was invoked."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from launcher import runtime_env


class ExecCalled(Exception):
    """Sentinel raised by the fake os.execve to inspect its arguments."""


def _make_venv(root: Path, directory: str = "venv") -> Path:
    python = root / directory / "bin" / "python"
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text("", encoding="utf-8")
    return python


def test_venv_python_finds_both_layouts(tmp_path):
    python = _make_venv(tmp_path)
    assert runtime_env.venv_python(tmp_path) == python

    dot_venv = _make_venv(tmp_path, ".venv")
    other = tmp_path / "other"
    assert runtime_env.venv_python(other) is None
    assert runtime_env.venv_python(tmp_path) == python  # venv/ wins over .venv/

    (tmp_path / "venv").rename(tmp_path / "venv-old")
    assert runtime_env.venv_python(tmp_path) == dot_venv


def test_prepend_scripts_to_path_is_idempotent(monkeypatch, tmp_path):
    python = _make_venv(tmp_path)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    runtime_env.prepend_scripts_to_path(tmp_path)
    runtime_env.prepend_scripts_to_path(tmp_path)

    parts = os.environ["PATH"].split(os.pathsep)
    assert parts[0] == str(python.parent)
    assert parts.count(str(python.parent)) == 1


def test_ensure_venv_reexecs_with_venv_python(monkeypatch, tmp_path):
    python = _make_venv(tmp_path)
    monkeypatch.setattr(runtime_env, "in_venv", lambda: False)
    monkeypatch.delenv(runtime_env.SKIP_REEXEC_ENV, raising=False)
    monkeypatch.delenv(runtime_env.REEXEC_MARKER, raising=False)
    monkeypatch.setattr(sys, "argv", ["manage.py", "server", "run"])
    calls = []

    def fake_execve(path, argv, env):
        calls.append((path, argv, env))
        raise ExecCalled

    monkeypatch.setattr(os, "execve", fake_execve)

    with pytest.raises(ExecCalled):
        runtime_env.ensure_venv(tmp_path)

    assert calls[0][0] == str(python)
    assert calls[0][1] == [str(python), os.path.abspath("manage.py"), "server", "run"]
    assert calls[0][2][runtime_env.REEXEC_MARKER] == str(python)
    assert calls[0][2]["VIRTUAL_ENV"] == str(python.parent.parent)
    assert calls[0][2]["PATH"].split(os.pathsep)[0] == str(python.parent)


@pytest.mark.parametrize("guard", ["in_venv", "marker", "skip"])
def test_ensure_venv_does_not_reexec_when_guarded(monkeypatch, tmp_path, guard):
    python = _make_venv(tmp_path)
    monkeypatch.setattr(runtime_env, "in_venv", lambda: guard == "in_venv")
    monkeypatch.delenv(runtime_env.SKIP_REEXEC_ENV, raising=False)
    monkeypatch.delenv(runtime_env.REEXEC_MARKER, raising=False)
    if guard == "marker":
        monkeypatch.setenv(runtime_env.REEXEC_MARKER, str(python))
    if guard == "skip":
        monkeypatch.setenv(runtime_env.SKIP_REEXEC_ENV, "1")

    calls = []

    def fake_execve(*args):
        calls.append(args)

    monkeypatch.setattr(os, "execve", fake_execve)

    assert runtime_env.ensure_venv(tmp_path) is (guard == "in_venv")
    assert calls == []


def test_ensure_venv_without_venv_is_a_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_env, "venv_python", lambda root=None: None)
    monkeypatch.setattr(os, "execve", lambda *args: pytest.fail("should not re-exec"))

    assert runtime_env.ensure_venv(tmp_path) is False
