"""Platform-independent startup of the server components."""

from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings

from launcher import runtime_env
from launcher.management.commands import server as server_module
from launcher.management.commands.server import Command


def test_worker_command_uses_configured_pool(settings):
    settings.AGENTONE_CELERY_POOL = "threads"
    settings.AGENTONE_CELERY_CONCURRENCY = 8

    command = Command._celery_worker_command("DEBUG", settings)

    assert command[0] == runtime_env.current_python(settings.BASE_DIR)
    assert command[1:9] == ['-m', 'celery', '-A', 'config', 'worker', '-l', 'DEBUG', '-E']
    assert command[9:] == ['--pool', 'threads', '--concurrency', '8']


def test_worker_command_defaults_to_prefork(settings):
    if hasattr(settings, "AGENTONE_CELERY_POOL"):
        del settings.AGENTONE_CELERY_POOL
    if hasattr(settings, "AGENTONE_CELERY_CONCURRENCY"):
        del settings.AGENTONE_CELERY_CONCURRENCY

    command = Command._celery_worker_command("INFO", settings)

    assert command[9:] == ['--pool', 'prefork', '--concurrency', '32']


def test_prepare_runtime_env_fixes_service_cwd_and_path(monkeypatch, tmp_path):
    original = Path.cwd()
    fake_python = tmp_path / "venv" / "Scripts" / "python.exe"
    monkeypatch.setattr(settings, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(server_module.sys, "executable", str(fake_python))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    try:
        Command._prepare_runtime_env()
        assert Path.cwd() == tmp_path
        assert os.environ["PATH"] == f"{fake_python.parent}{os.pathsep}/usr/bin:/bin"

        # Calling twice must not keep prepending the same directory.
        Command._prepare_runtime_env()
        assert os.environ["PATH"].count(str(fake_python.parent)) == 1
    finally:
        os.chdir(original)


def test_default_pool_setting_is_valid():
    assert settings.AGENTONE_CELERY_POOL in ("threads", "prefork", "solo", "gevent", "eventlet")
