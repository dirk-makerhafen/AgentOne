"""Tests for ``.memory_sources.md`` hashing, rendering and merge helpers."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from server.tests.memory_test_support import paths as mempaths
from server.tests.memory_test_support import sources as memsources


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
                "changed_chars": 12,
                "depth": 3,
                "is_up_to_date": False,
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_write_sources_roundtrip_and_idempotent(tmp_path):
    path = tmp_path / memsources.SOURCES_FILENAME
    payload = _payload()
    assert memsources.write_sources(path, payload) is True
    assert memsources.write_sources(path, payload) is False

    loaded = memsources.read_sources(path)
    assert loaded["kind"] == "task"
    assert loaded["sources"][0]["current_hash"] == "sha256:abc"
    assert loaded["sources"][0]["last_processed_hash"] is None
    assert loaded["sources"][0]["changed_chars"] == 12
    assert loaded["sources"][0]["depth"] == 3
    assert loaded["sources"][0]["is_up_to_date"] is False
    assert "hours_since_processed" not in loaded["sources"][0]
    assert "generated_at" in loaded
    assert "| Path | Last processed |" in path.read_text()
    assert "| Depth | Upstream |" in path.read_text()
    assert "| waiting |" in path.read_text()


def test_previous_hashes_matches_path():
    previous = memsources.previous_hashes(_payload())
    assert previous["sessions/"] is None

    payload = _payload()
    payload["sources"][0]["last_processed_hash"] = "sha256:old"
    previous = memsources.previous_hashes(payload)
    assert previous["sessions/"] == "sha256:old"


def test_report_filename_uses_canonical_name():
    from server.models.enums.message_enums import MessageType

    message = SimpleNamespace(
        pk=9,
        message_type=MessageType.REFLECTION,
        created_at=datetime(2026, 10, 23, 14, 5, 6),
    )
    assert mempaths.report_filename(message) == "reflections.md"
    assert mempaths.report_filename(message) == "reflections.md"

    message.message_type = MessageType.COMPACTION
    assert mempaths.report_filename(message) == "compaction.md"


def test_legacy_report_files_only_matches_timestamped_names(tmp_path):
    legacy = tmp_path / "compaction_20261031-103959_152472.md"
    legacy.write_text("old", encoding="utf-8")
    other_legacy = tmp_path / "reflections_20261031-103959_152472.md"
    other_legacy.write_text("old", encoding="utf-8")
    (tmp_path / "compaction.md").write_text("new", encoding="utf-8")
    (tmp_path / "notes_20261031-103959_1.md").write_text("keep", encoding="utf-8")

    found = {path.name for path in mempaths.legacy_report_files(tmp_path)}

    assert found == {legacy.name, other_legacy.name}


def test_previous_by_identity_tracks_child_scopes():
    manifest = {
        "sources": [
            {"path": "/old/project", "pk": 7,
             "type": "project", "last_processed_hash": "a" * 40},
            {"path": "/old/workspace", "pk": 9,
             "type": "workspace", "last_processed_hash": "b" * 40},
            {"path": "agents/", "last_processed_hash": "c" * 40},
        ]
    }
    by_identity = memsources.previous_by_identity(manifest)
    assert by_identity[7] == "a" * 40
    assert by_identity[9] == "b" * 40
    # directory sources have no pk, so they don't appear in by_identity
    assert 0 not in by_identity
