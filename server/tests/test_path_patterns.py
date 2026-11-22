"""Windows path forms must not slip past policy checks."""

from __future__ import annotations

import pytest

from runtime import guardrails, path_patterns
from runtime.guidance_files import _reject_escape
from runtime.workspace_access import _has_path_escape, _is_external_scope


@pytest.mark.parametrize(
    "token",
    [
        "/etc/passwd", "~/secret", "$HOME/secret", "${HOME}/secret",
        r"C:\Users\me\secret", r"D:relative\secret", r"\\server\share\file",
        r"%USERPROFILE%\secret", r"%TEMP%\x", "$env:USERPROFILE\\secret",
    ],
)
def test_absolute_forms_are_recognized_on_every_host(token):
    assert path_patterns.is_absolute(token) is True
    assert guardrails._is_absolute_path(token) is True


@pytest.mark.parametrize("token", ["docs/readme.md", "./data", "_tmp\\file", "", "  "])
def test_relative_forms_are_not_absolute(token):
    assert path_patterns.is_absolute(token) is False


@pytest.mark.parametrize(
    "pattern", ["../secret", r"..\..\secret", "a/../b", r"a\..\b"]
)
def test_traversal_is_recognized_with_both_separators(pattern):
    assert path_patterns.has_traversal(pattern) is True
    assert _has_path_escape(pattern) is True


def test_scope_validation_treats_windows_paths_as_external():
    assert _is_external_scope(r"C:\temp\*") is True
    assert _is_external_scope(r"\\server\share\*") is True
    assert _is_external_scope("%USERPROFILE%\\*") is True
    assert _is_external_scope("inbox/**") is False


def test_guardrail_shell_targets_windows_paths(monkeypatch):
    monkeypatch.setattr(guardrails.sys, "platform", "win32")

    targets = guardrails._shell_targets(r'type "C:\secrets\key.txt"')

    assert targets == [(r"C:\secrets\key.txt", "read")]


def test_guardrail_redirect_target_windows_path(monkeypatch):
    monkeypatch.setattr(guardrails.sys, "platform", "win32")

    targets = guardrails._shell_targets(r"echo hi > C:\temp\out.txt")

    assert targets == [(r"C:\temp\out.txt", "write")]


def test_autoload_patterns_reject_windows_absolute_and_traversal():
    with pytest.raises(ValueError, match="relative"):
        _reject_escape(r"C:\Users\me\AGENTS.md", "agent.md")
    with pytest.raises(ValueError, match=r"\.\."):
        _reject_escape(r"..\..\AGENTS.md", "agent.md")
