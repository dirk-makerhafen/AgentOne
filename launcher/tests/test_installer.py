"""Tests for the standalone, cross-platform install.py bootstrap."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("agentone_installer", ROOT / "install.py")
installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(installer)


def fake_environment(monkeypatch, tmp_path, *, existing=True):
    """Patch out every side effect and return the recorded calls + target."""
    target = tmp_path / "AgentOne"
    if existing:
        (target / ".git").mkdir(parents=True)
        (target / "config").mkdir()
        (target / "config" / "settings_local.py").write_text("", encoding="utf-8")
        (target / "requirements.txt").write_text("Django\n", encoding="utf-8")

    calls = []

    def fake_run(args, *, cwd=None, capture=False):
        command = [str(part) for part in args]
        calls.append((command, cwd))
        if command[:2] == ["git", "clone"]:
            clone_dir = Path(command[-1])
            (clone_dir / ".git").mkdir(parents=True, exist_ok=True)
            (clone_dir / "requirements.txt").write_text("Django\n", encoding="utf-8")
        return ""

    python = target / "venv" / "bin" / "python"
    monkeypatch.setattr(installer, "_run", fake_run)
    monkeypatch.setattr(installer, "ensure_venv", lambda root: python)
    monkeypatch.setattr(installer.shutil, "which", lambda name: "/usr/bin/git" if name == "git" else None)
    monkeypatch.setattr(installer, "redis_reachable", lambda: True)
    return calls, target


def _commands(calls):
    return [call[0] for call in calls]


def test_install_runs_full_bootstrap(monkeypatch, tmp_path):
    calls, target = fake_environment(monkeypatch, tmp_path)

    assert installer.main(["--dir", str(target)]) == 0

    commands = _commands(calls)
    pip = [cmd[1:] for cmd in commands if "-m" in cmd and cmd[1] == "-m"]
    assert ["pip", "install", "--upgrade", "pip"] in [rest[1:] for rest in pip]
    assert any(cmd[1:5] == ["manage.py", "migrate", "--noinput"] for cmd in commands)
    assert any(cmd[1:5] == ["manage.py", "collectstatic", "--noinput"] for cmd in commands)
    assert any(cmd[1:] == ["manage.py", "reload_all"] for cmd in commands)
    assert not any(cmd[1:4] == ["manage.py", "server", "setup"] for cmd in commands)
    assert all(cwd == target for _, cwd in calls)

    def index(predicate):
        return next(i for i, cmd in enumerate(commands) if predicate(cmd))

    assert index(lambda cmd: "-m" in cmd and "pip" in cmd) < index(lambda cmd: "migrate" in cmd)
    assert index(lambda cmd: "migrate" in cmd) < index(lambda cmd: "collectstatic" in cmd)
    assert index(lambda cmd: "collectstatic" in cmd) < index(lambda cmd: "reload_all" in cmd)


def test_fresh_checkout_is_cloned_and_set_up(monkeypatch, tmp_path):
    calls, target = fake_environment(monkeypatch, tmp_path, existing=False)

    assert installer.main(["--dir", str(target), "--branch", "develop"]) == 0

    clone = calls[0][0]
    assert clone[:3] == ["git", "clone", "--branch"]
    assert "develop" in clone
    assert any(cmd[1:4] == ["manage.py", "server", "setup"] for cmd in _commands(calls))


def test_non_empty_non_git_directory_is_refused(monkeypatch, tmp_path):
    target = tmp_path / "occupied"
    target.mkdir()
    (target / "random.txt").write_text("keep me", encoding="utf-8")
    fake_environment(monkeypatch, tmp_path)

    with pytest.raises(installer.InstallError, match="not empty"):
        installer.main(["--dir", str(target)])

    assert (target / "random.txt").read_text(encoding="utf-8") == "keep me"


def test_browser_is_installed_by_default(monkeypatch, tmp_path):
    calls, target = fake_environment(monkeypatch, tmp_path, existing=False)

    assert installer.main(["--dir", str(target)]) == 0

    assert any(cmd[1:5] == ["manage.py", "server", "browser", "fetch"] for cmd in _commands(calls))


def test_skip_browser(monkeypatch, tmp_path):
    calls, target = fake_environment(monkeypatch, tmp_path, existing=False)

    assert installer.main(["--dir", str(target), "--skip-browser"]) == 0

    assert not any("browser" in cmd for cmd in _commands(calls))


def test_with_browser_is_a_deprecated_noop(monkeypatch, tmp_path):
    calls, target = fake_environment(monkeypatch, tmp_path, existing=False)

    assert installer.main(["--dir", str(target), "--with-browser"]) == 0

    # Compatibility flag still installs exactly one browser (the default one).
    fetches = [cmd for cmd in _commands(calls) if cmd[1:5] == ["manage.py", "server", "browser", "fetch"]]
    assert len(fetches) == 1


def test_requirements_missing_is_an_error(monkeypatch, tmp_path):
    calls, target = fake_environment(monkeypatch, tmp_path)
    (target / "requirements.txt").unlink()

    with pytest.raises(installer.InstallError, match="requirements.txt"):
        installer.main(["--dir", str(target)])

    assert not any("manage.py" in cmd for cmd in _commands(calls))


def test_windows_prepares_terminal_bins(monkeypatch, tmp_path):
    _, target = fake_environment(monkeypatch, tmp_path)
    prepared = []
    monkeypatch.setattr(installer, "prepare_terminal_bins", lambda root: prepared.append(root))
    monkeypatch.setattr(installer.sys, "platform", "win32")

    assert installer.main(["--dir", str(target)]) == 0
    assert prepared == [target]


def test_skip_terminal_binaries(monkeypatch, tmp_path):
    _, target = fake_environment(monkeypatch, tmp_path)
    prepared = []
    monkeypatch.setattr(installer, "prepare_terminal_bins", lambda root: prepared.append(root))

    assert installer.main(["--dir", str(target), "--skip-terminal-binaries"]) == 0
    assert prepared == []


def test_windows_venv_layout(monkeypatch, tmp_path):
    monkeypatch.setattr(installer.sys, "platform", "win32")

    assert installer.venv_python(tmp_path) == tmp_path / "venv" / "Scripts" / "python.exe"


def test_ensure_venv_creates_environment(monkeypatch, tmp_path):
    created = []

    class FakeEnvBuilder:
        def __init__(self, **kwargs):
            created.append(kwargs)

        def create(self, path):
            scripts = Path(path) / ("Scripts" if installer.sys.platform == "win32" else "bin")
            scripts.mkdir(parents=True)
            (scripts / ("python.exe" if installer.sys.platform == "win32" else "python")).write_text("")

    monkeypatch.setattr(installer.venv, "EnvBuilder", FakeEnvBuilder)

    python = installer.ensure_venv(tmp_path)

    assert created == [{"with_pip": True}]
    assert python.exists()
