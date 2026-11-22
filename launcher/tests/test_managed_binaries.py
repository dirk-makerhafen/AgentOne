"""Managed psmux/tmux and Git Bash discovery."""
from __future__ import annotations

import hashlib
import io
import os
import zipfile
from pathlib import Path

import pytest

from runtime import managed_binaries as mb


def _zip_with_tmux(payload: bytes = b"fake tmux.exe") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        zipped.writestr("LICENSE", "MIT")
        zipped.writestr("tmux.exe", payload)
    return buffer.getvalue()


def test_managed_tmux_path_uses_bin_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(mb, "bin_dir", lambda: tmp_path / "bin")
    monkeypatch.setattr(mb.os, "name", "nt")

    assert mb.managed_tmux_path() == tmp_path / "bin" / "tmux.exe"


def test_ensure_tmux_is_noop_on_posix(monkeypatch, tmp_path):
    monkeypatch.setattr(mb, "bin_dir", lambda: tmp_path / "bin")
    monkeypatch.setattr(mb.sys, "platform", "darwin")

    assert mb.ensure_tmux() is None
    assert not (tmp_path / "bin").exists()


def test_ensure_tmux_downloads_verifies_and_extracts(monkeypatch, tmp_path):
    archive = _zip_with_tmux()
    monkeypatch.setattr(mb, "bin_dir", lambda: tmp_path / "bin")
    monkeypatch.setattr(mb, "managed_tmux_path", lambda: tmp_path / "bin" / "tmux.exe")
    monkeypatch.setattr(mb.sys, "platform", "win32")
    monkeypatch.setattr(mb.platform, "machine", lambda: "AMD64")
    monkeypatch.setitem(mb._PSMUX_ZIP_SHA256, "x64", hashlib.sha256(archive).hexdigest())

    urls = []

    def fake_urlopen(url, timeout):
        urls.append((url, timeout))
        return io.BytesIO(archive)

    monkeypatch.setattr(mb.urllib.request, "urlopen", fake_urlopen)

    target = mb.ensure_tmux()

    assert target == tmp_path / "bin" / "tmux.exe"
    assert target.read_bytes() == b"fake tmux.exe"
    assert urls[0][0] == (
        f"https://github.com/psmux/psmux/releases/download/v{mb.PSMUX_VERSION}/"
        f"psmux-v{mb.PSMUX_VERSION}-windows-x64.zip"
    )
    # A second call is a no-op and does not re-download.
    assert mb.ensure_tmux() == target
    assert len(urls) == 1


def test_ensure_tmux_rejects_bad_checksum(monkeypatch, tmp_path):
    monkeypatch.setattr(mb, "bin_dir", lambda: tmp_path / "bin")
    monkeypatch.setattr(mb, "managed_tmux_path", lambda: tmp_path / "bin" / "tmux.exe")
    monkeypatch.setattr(mb.sys, "platform", "win32")
    monkeypatch.setattr(mb.platform, "machine", lambda: "x86_64")
    monkeypatch.setitem(mb._PSMUX_ZIP_SHA256, "x64", "0" * 64)
    monkeypatch.setattr(mb.urllib.request, "urlopen", lambda url, timeout: io.BytesIO(_zip_with_tmux()))

    with pytest.raises(mb.ManagedBinaryError, match="checksum mismatch"):
        mb.ensure_tmux()
    assert not (tmp_path / "bin" / "tmux.exe").exists()


def test_resolve_tmux_binary_prefers_override_and_managed_path(monkeypatch, tmp_path):
    monkeypatch.setattr(mb, "bin_dir", lambda: tmp_path / "bin")
    monkeypatch.setattr(mb, "managed_tmux_path", lambda: tmp_path / "bin" / "tmux.exe")
    monkeypatch.setattr(mb.sys, "platform", "darwin")
    monkeypatch.delenv("AGENTONE_TMUX_BINARY", raising=False)
    monkeypatch.setattr(mb.shutil, "which", lambda name: None)

    managed = tmp_path / "bin" / "tmux.exe"
    managed.parent.mkdir(parents=True)
    managed.write_bytes(b"")
    assert mb.resolve_tmux_binary() == str(managed)

    override = tmp_path / "custom-tmux"
    override.write_bytes(b"")
    monkeypatch.setenv("AGENTONE_TMUX_BINARY", str(override))
    assert mb.resolve_tmux_binary() == str(override)


def test_resolve_tmux_binary_uses_path_aliases(monkeypatch, tmp_path):
    monkeypatch.setattr(mb, "bin_dir", lambda: tmp_path / "bin")
    monkeypatch.setattr(mb.sys, "platform", "darwin")
    monkeypatch.delenv("AGENTONE_TMUX_BINARY", raising=False)
    monkeypatch.setattr(mb.shutil, "which", lambda name: "/usr/bin/psmux" if name == "psmux" else None)

    assert mb.resolve_tmux_binary() == "/usr/bin/psmux"


def test_resolve_skips_auto_install_after_recent_failure(monkeypatch, tmp_path):
    bin_path = tmp_path / "bin"
    bin_path.mkdir()
    (bin_path / ".tmux.download.failed").write_text("offline", encoding="utf-8")
    monkeypatch.setattr(mb, "bin_dir", lambda: bin_path)
    monkeypatch.setattr(mb, "managed_tmux_path", lambda: bin_path / "tmux.exe")
    monkeypatch.setattr(mb.sys, "platform", "win32")
    monkeypatch.setattr(mb.shutil, "which", lambda name: None)
    called = []
    monkeypatch.setattr(mb, "ensure_tmux", lambda: called.append(True))

    assert mb.resolve_tmux_binary() is None
    assert called == []


def test_resolve_bash_from_git_exec_path(monkeypatch, tmp_path):
    bash = tmp_path / "bin" / "bash.exe"
    bash.parent.mkdir(parents=True)
    bash.write_bytes(b"")
    git_exec = tmp_path / "mingw64" / "libexec" / "git-core"

    monkeypatch.setattr(mb.sys, "platform", "win32")
    monkeypatch.delenv("AGENTONE_BASH", raising=False)
    monkeypatch.setattr(mb.shutil, "which", lambda name: "C:\\Git\\cmd\\git.exe" if name in ("git", "git.exe") else None)

    class FakeResult:
        stdout = str(git_exec)

    monkeypatch.setattr(mb.subprocess, "run", lambda *args, **kwargs: FakeResult())

    assert mb.resolve_bash() == str(bash)


def test_resolve_bash_override(monkeypatch, tmp_path):
    custom = tmp_path / "bash"
    custom.write_bytes(b"")
    monkeypatch.setenv("AGENTONE_BASH", str(custom))

    assert mb.resolve_bash() == str(custom)
