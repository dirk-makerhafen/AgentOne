"""Version reporting: git describe, VERSION fallback and remote checks."""

from __future__ import annotations

import pytest

from runtime import version as version_module


@pytest.fixture
def fake_cache(monkeypatch):
    store = {}
    monkeypatch.setattr(version_module, "_cache_get", lambda key: store.get(key))
    monkeypatch.setattr(version_module, "_cache_set", lambda key, value, ttl: store.__setitem__(key, value))
    monkeypatch.setattr(version_module, "_cache_delete", lambda *keys: [store.pop(k, None) for k in keys])
    return store


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    return tmp_path


def _git_results(monkeypatch, mapping):
    def fake_git(args, root, timeout=10):
        return mapping.get(tuple(args), "")

    monkeypatch.setattr(version_module, "_git", fake_git)


def _base_results(overrides=None):
    results = {
        ("describe", "--tags", "--always", "--dirty"): "v2.3.1",
        ("rev-parse", "HEAD"): "abcdef1234567890",
        ("rev-parse", "--short", "HEAD"): "abcdef1",
        ("rev-parse", "--abbrev-ref", "HEAD"): "main",
        ("status", "--porcelain"): "",
    }
    results.update(overrides or {})
    return results


def test_version_uses_release_tag_when_present(monkeypatch, fake_cache, repo):
    _git_results(monkeypatch, _base_results())

    info = version_module.get_version_info(repo)

    assert info["version"] == "2.3.1"
    assert info["source"] == "git"
    assert info["dirty"] is False
    assert fake_cache[version_module._LOCAL_CACHE_KEY]["version"] == "2.3.1"


def test_version_falls_back_to_version_file_plus_commit(monkeypatch, fake_cache, repo):
    _git_results(monkeypatch, _base_results({
        ("describe", "--tags", "--always", "--dirty"): "abcdef1-dirty",
        ("status", "--porcelain"): " M some_file",
    }))

    info = version_module.get_version_info(repo, refresh=True)

    assert info["version"] == "0.1.0+abcdef1-dirty"
    assert info["dirty"] is True


def test_version_without_git_uses_file(monkeypatch, fake_cache, tmp_path):
    (tmp_path / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    monkeypatch.setattr(version_module, "_git", lambda *args, **kwargs: None)

    info = version_module.get_version_info(tmp_path, refresh=True)

    assert info["version"] == "9.9.9"
    assert info["source"] == "file"
    assert info["is_git"] is False


def test_remote_check_is_not_performed_on_page_render(monkeypatch, fake_cache, repo):
    def fake_git(args, root, timeout=10):
        if args and args[0] in ("fetch", "ls-remote"):
            raise AssertionError("network must not be touched without refresh=True")
        return ""

    monkeypatch.setattr(version_module, "_git", fake_git)

    assert version_module.get_remote_commit(repo) == ""
    assert version_module.update_status(repo)["remote_commit"] == ""


def test_update_status_reports_behind_count(monkeypatch, fake_cache, repo):
    _git_results(monkeypatch, _base_results({
        ("rev-parse", "origin/main"): "bbbbbbbbbbbbbbbb",
        ("rev-list", "--count", "HEAD..origin/main"): "2",
    }))

    status = version_module.update_status(repo, refresh=True)

    assert status["available"] is True
    assert status["behind"] == 2
    assert status["remote_short_commit"] == "bbbbbbb"


def test_locally_ahead_checkout_is_not_an_update(monkeypatch, fake_cache, repo):
    _git_results(monkeypatch, _base_results({
        ("rev-parse", "origin/main"): "aaaaaaaaaaaaaaaa",
        ("rev-list", "--count", "HEAD..origin/main"): "0",
    }))

    status = version_module.update_status(repo, refresh=True)

    assert status["available"] is False
    assert status["behind"] == 0


def test_remote_commit_falls_back_to_lsremote(monkeypatch, fake_cache, repo):
    calls = []

    def fake_git(args, root, timeout=10):
        calls.append(tuple(args))
        if args[:2] == ["rev-parse", "--abbrev-ref"]:
            return "main"
        if args[:2] == ["rev-parse", "origin/main"]:
            return ""
        if args[:4] == ["ls-remote", "--exit-code", "--heads", "origin"]:
            return "cccccccccccccccc\trefs/heads/main"
        return ""

    monkeypatch.setattr(version_module, "_git", fake_git)

    assert version_module.get_remote_commit(repo, refresh=True) == "cccccccccccccccc"
    assert ("ls-remote", "--exit-code", "--heads", "origin", "main") in calls
