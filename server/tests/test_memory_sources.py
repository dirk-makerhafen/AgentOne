"""Tests for ``.memory_sources.md`` hashing, rendering and merge helpers."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from runtime.memory import paths as mempaths
from runtime.memory import sources as memsources


def _payload(**overrides):
    payload = {
        "kind": "task",
        "key": "default",
        "name": "task_default",
        "sources": [
            {
                "path": "sessions/",
                "last_processed_hash": None,
                "current_hash": "sha256:abc",
                "hours_since_processed": 1.5,
                "changed_chars": 12,
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_hash_files_ignores_metadata_and_is_order_independent(tmp_path):
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "b.md").write_text("b")
    (tmp_path / ".gitignore").write_text("ignored")
    (tmp_path / memsources.SOURCES_FILENAME).write_text("ignored")
    (tmp_path / "x.pyc").write_text("ignored")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "c.py").write_text("ignored")

    first = memsources.hash_files([tmp_path / "a.md", tmp_path / "b.md"], base=tmp_path)
    second = memsources.hash_files([tmp_path / "b.md", tmp_path / "a.md"], base=tmp_path)
    assert first == second
    assert first and first.startswith("sha256:")


def test_hash_files_changes_on_rename_and_content(tmp_path):
    (tmp_path / "a.md").write_text("a")
    original = memsources.hash_files([tmp_path / "a.md"], base=tmp_path)
    (tmp_path / "a.md").rename(tmp_path / "b.md")
    assert memsources.hash_files([tmp_path / "b.md"], base=tmp_path) != original
    (tmp_path / "b.md").write_text("changed")
    assert memsources.hash_files([tmp_path / "b.md"], base=tmp_path) != original


def test_hash_files_empty_returns_none(tmp_path):
    assert memsources.hash_files([], base=tmp_path) is None
    assert memsources.hash_files([tmp_path / "missing.md"], base=tmp_path) is None


def test_write_sources_roundtrip_and_idempotent(tmp_path):
    path = tmp_path / memsources.SOURCES_FILENAME
    payload = _payload()
    assert memsources.write_sources(path, payload) is True
    assert memsources.write_sources(path, payload) is False

    loaded = memsources.read_sources(path)
    assert loaded["kind"] == "task"
    assert loaded["sources"][0]["current_hash"] == "sha256:abc"
    assert loaded["sources"][0]["last_processed_hash"] is None
    assert loaded["sources"][0]["hours_since_processed"] == 1.5
    assert loaded["sources"][0]["changed_chars"] == 12
    assert "generated_at" in loaded
    assert "| Path | Last processed |" in path.read_text()


def test_previous_hashes_matches_path():
    previous = memsources.previous_hashes(_payload())
    assert previous["sessions/"] is None

    payload = _payload()
    payload["sources"][0]["last_processed_hash"] = "sha256:old"
    previous = memsources.previous_hashes(payload)
    assert previous["sessions/"] == "sha256:old"


def test_report_filename_uses_reflection_type_and_message_pk():
    from server.models.enums.message_enums import MessageType

    message = SimpleNamespace(
        pk=9,
        message_type=MessageType.REFLECTION,
        created_at=datetime(2026, 10, 23, 14, 5, 6),
    )
    assert mempaths.report_filename(message) == "reflections_20261023-140506_9.md"
    assert mempaths.report_filename(message) == "reflections_20261023-140506_9.md"

    message.message_type = MessageType.COMPACTION
    assert mempaths.report_filename(message) == "compaction_20261023-140506_9.md"


def test_previous_by_identity_tracks_child_scopes():
    manifest = {
        "sources": [
            {"path": "/old/project", "kind": "project", "pk": 7,
             "last_processed_hash": "a" * 40},
            {"path": "/old/workspace", "kind": "workspace", "pk": 9,
             "last_processed_hash": "b" * 40},
            {"path": "agents/", "last_processed_hash": "c" * 40},
        ]
    }
    by_identity = memsources.previous_by_identity(manifest)
    assert by_identity[("project", 7)] == "a" * 40
    assert by_identity[("workspace", 9)] == "b" * 40
    assert memsources.source_identity({"kind": "project", "pk": "7"}) == (
        "project", 7,
    )
    assert memsources.source_identity({"path": "agents/"}) is None
