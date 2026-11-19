"""Tests for the playbook / improvement-proposal schema and normalization."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from server.tests.memory_test_support import finalize as memfinalize
from server.tests.memory_test_support import playbook as memplaybook
from server.tests.memory_test_support import sources as memsources


# ---------------------------------------------------------------------------
# Directive normalization
# ---------------------------------------------------------------------------


def test_fingerprint_ignores_case_and_punctuation():
    first = memplaybook.fingerprint_for("Stop calling memory_merge after 2 empties!")
    second = memplaybook.fingerprint_for("stop calling   memory_merge after 2 empties")
    assert first == second
    assert first.startswith("stop-calling-memory-merge")


def test_directive_requires_a_rule():
    assert memplaybook.normalize_directive({"trigger": "x"}) is None
    assert memplaybook.normalize_directive("not a mapping") is None


def test_directive_gets_stable_id_and_defaults():
    directive = memplaybook.normalize_directive(
        {"rule": "Check the manifest before retrying.", "routing": "instructions"}
    )

    assert directive["id"].startswith("PB-")
    assert directive["routing"] == "prompt"
    assert directive["status"] == "candidate"
    assert directive["fingerprint"]


def test_active_without_support_is_clamped_to_candidate():
    directive = memplaybook.normalize_directive(
        {"rule": "Never retry a failed call.", "status": "active"}
    )
    assert directive["status"] == "candidate"


def test_active_with_evidence_stays_active():
    directive = memplaybook.normalize_directive(
        {
            "rule": "Never retry a failed call.",
            "status": "active",
            "evidence": ["session:12"],
        }
    )
    assert directive["status"] == "active"
    assert directive["support"] == 1


def test_unknown_status_and_routing_fall_back():
    directive = memplaybook.normalize_directive(
        {"rule": "Do the thing.", "status": "maybe", "routing": "vibes"}
    )
    assert directive["status"] == "candidate"
    assert directive["routing"] == "prompt"


def test_directives_dedupe_by_fingerprint_and_merge_evidence():
    directives = memplaybook.normalize_directives(
        [
            {
                "rule": "Stop after two empty dispatches.",
                "support": 1,
                "evidence": ["session:1"],
            },
            {
                "rule": "stop after two empty dispatches",
                "support": 3,
                "status": "active",
                "evidence": ["session:2", "session:1"],
            },
        ]
    )

    assert len(directives) == 1
    merged = directives[0]
    assert merged["support"] == 3
    assert merged["status"] == "active"
    assert merged["evidence"] == ["session:1", "session:2"]


def test_directives_are_capped_with_active_first():
    raw = [
        {"rule": f"candidate rule {index}", "status": "candidate"}
        for index in range(memplaybook.MAX_DIRECTIVES + 5)
    ]
    raw.append({"rule": "important rule", "status": "active", "support": 2})

    directives = memplaybook.normalize_directives(raw)

    assert len(directives) == memplaybook.MAX_DIRECTIVES
    assert directives[0]["rule"] == "important rule"


# ---------------------------------------------------------------------------
# File parsing / normalization
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_legacy_playbook_has_no_directives(tmp_path):
    path = _write(tmp_path / "reflection.md", "# Lessons\n\nPlain prose.")

    loaded = memplaybook.load_playbook(path)

    assert loaded["present"] is True
    assert loaded["legacy"] is True
    assert loaded["directives"] == []


def test_missing_playbook_is_not_an_error(tmp_path):
    loaded = memplaybook.load_playbook(tmp_path / "reflection.md")
    assert loaded["present"] is False
    assert loaded["legacy"] is False


def test_wrong_schema_is_rejected(tmp_path):
    path = _write(
        tmp_path / "reflection.md",
        "---\nschema: agentone.playbook/999\ndirectives: []\n---\n",
    )
    with pytest.raises(memplaybook.PlaybookError):
        memplaybook.load_playbook(path)


def test_directives_must_be_a_list(tmp_path):
    path = _write(
        tmp_path / "reflection.md",
        "---\nschema: agentone.playbook/1\ndirectives: nope\n---\n",
    )
    with pytest.raises(memplaybook.PlaybookError):
        memplaybook.load_playbook(path)


def test_malformed_yaml_is_rejected(tmp_path):
    path = _write(
        tmp_path / "reflection.md",
        "---\nschema: [unclosed\ndirectives: []\n---\n",
    )
    with pytest.raises(memplaybook.PlaybookError):
        memplaybook.load_playbook(path)


def test_unquoted_colon_in_rule_is_repaired(tmp_path):
    """The synthesizer's ``rule: text with: a colon`` must not wedge a node."""
    path = _write(
        tmp_path / "reflection.md",
        "---\n"
        "schema: agentone.playbook/1\n"
        "directives:\n"
        "- id: PB-test\n"
        "  rule: After each batch (unless 'do not continue'): retry. Type: daily_summary first.\n"
        "  trigger: batching\n"
        "---\n",
    )
    info: dict[str, bool] = {}

    loaded = memplaybook.load_playbook(path, info)

    assert info == {"repaired": True}
    assert len(loaded["directives"]) == 1
    assert loaded["directives"][0]["rule"].startswith("After each batch")

    report = memplaybook.normalize_reflection(path)
    assert report["changed"] is True
    # The rewrite by safe_dump makes the fix permanent, so a later read needs
    # no repair at all.
    reread_info: dict[str, bool] = {}
    memplaybook.load_playbook(path, reread_info)
    assert reread_info == {}


def test_repair_info_is_absent_for_valid_yaml(tmp_path):
    path = _write(
        tmp_path / "reflection.md",
        "---\nschema: agentone.playbook/1\ndirectives: []\n---\n",
    )
    info: dict[str, bool] = {}
    memplaybook.load_playbook(path, info)
    assert info == {}


def test_unrepairable_yaml_still_rejected(tmp_path):
    path = _write(
        tmp_path / "reflection.md",
        "---\nschema: [unclosed\ndirectives: []\n---\n",
    )
    with pytest.raises(memplaybook.PlaybookError):
        memplaybook.load_playbook(path, {})


def test_prose_starting_with_a_rule_is_still_legacy(tmp_path):
    path = _write(
        tmp_path / "reflection.md",
        "---\n\n# Lessons\n\nThis file opens with a horizontal rule.\n",
    )

    loaded = memplaybook.load_playbook(path)

    assert loaded["legacy"] is True
    assert loaded["directives"] == []


def test_normalize_reflection_rewrites_new_format(tmp_path):
    path = _write(
        tmp_path / "reflection.md",
        "---\n"
        "schema: agentone.playbook/1\n"
        "directives:\n"
        "  - rule: Stop looping.\n"
        "    status: active\n"
        "    evidence: [session:1]\n"
        "  - rule: stop looping\n"
        "    evidence: [session:2]\n"
        "---\n\nHuman notes stay.\n",
    )

    report = memplaybook.normalize_reflection(path)

    assert report["directives"] == 1
    assert report["changed"] is True
    reloaded = memplaybook.load_playbook(path)
    assert len(reloaded["directives"]) == 1
    assert "Human notes stay." in reloaded["body"]
    assert "schema: agentone.playbook/1" in path.read_text(encoding="utf-8")


def test_normalize_reflection_leaves_legacy_file_untouched(tmp_path):
    original = "# Old lessons\n\nDo better.\n"
    path = _write(tmp_path / "reflection.md", original)

    report = memplaybook.normalize_reflection(path)

    assert report["legacy"] is True
    assert report["changed"] is False
    assert path.read_text(encoding="utf-8") == original


def test_normalize_improvements_dedupes_and_caps(tmp_path):
    path = _write(
        tmp_path / "improvements.md",
        "---\n"
        "schema: agentone.improvements/1\n"
        "proposals:\n"
        "  - id: IMP-1\n"
        "    kind: harness\n"
        "    summary: Fix the settings override.\n"
        "  - kind: harness\n"
        "    summary: fix the settings override\n"
        "    detail: Pass access instead.\n"
        "---\n",
    )

    report = memplaybook.normalize_improvements(path)

    assert report["proposals"] == 1
    loaded = memplaybook.load_improvements(path)
    assert loaded["proposals"][0]["id"] == "IMP-1"
    assert loaded["proposals"][0]["detail"] == "Pass access instead."


def test_normalize_node_reports_malformed_playbook(tmp_path):
    _write(tmp_path / "memory.md", "facts")
    _write(
        tmp_path / "reflection.md",
        "---\nschema: other/1\ndirectives: []\n---\n",
    )

    ok, report = memplaybook.normalize_node(tmp_path)

    assert ok is False
    assert "invalid playbook" in report["message"]


def test_normalize_node_accepts_missing_and_legacy_files(tmp_path):
    _write(tmp_path / "memory.md", "facts")
    _write(tmp_path / "reflection.md", "legacy prose")

    ok, report = memplaybook.normalize_node(tmp_path)

    assert ok is True
    assert report["reflection"]["legacy"] is True
    assert report["improvements"]["present"] is False


# ---------------------------------------------------------------------------
# Finalize integration
# ---------------------------------------------------------------------------


def _node(tmp_path: Path) -> Path:
    folder = tmp_path / "task"
    folder.mkdir()
    memsources.write_sources(
        folder / memsources.SOURCES_FILENAME,
        {
            "kind": "task",
            "type": "global-agent-task",
            "key": "t",
            "name": "t",
            "sources": [
                {
                    "path": "sessions/",
                    "type": "global-agent-task-sessions",
                    "last_processed_hash": "a" * 40,
                    "current_hash": "b" * 40,
                }
            ],
        },
    )
    (folder / "memory.md").write_text("facts", encoding="utf-8")
    (folder / "reflection.md").write_text("lessons", encoding="utf-8")
    (folder / ".memory_inflight").write_text("{}", encoding="utf-8")
    return folder


def test_finalize_advances_and_normalizes_a_valid_playbook(tmp_path):
    folder = _node(tmp_path)
    _write(
        folder / "reflection.md",
        "---\n"
        "schema: agentone.playbook/1\n"
        "directives:\n"
        "  - rule: Stop after two empty dispatches.\n"
        "    status: active\n"
        "    evidence: [session:7]\n"
        "---\n",
    )

    with patch("tree.mark_processed", return_value=True) as mocked:
        ok, result = memfinalize.finalize_memory(folder.as_posix())

    assert ok is True
    assert result["playbook"]["reflection"]["directives"] == 1
    mocked.assert_called_once()
    reloaded = memplaybook.load_playbook(folder / "reflection.md")
    assert reloaded["directives"][0]["status"] == "active"


def test_finalize_refuses_malformed_playbook(tmp_path):
    folder = _node(tmp_path)
    _write(
        folder / "reflection.md",
        "---\nschema: agentone.playbook/2\ndirectives: []\n---\n",
    )

    with patch("tree.mark_processed", return_value=True) as mocked:
        ok, result = memfinalize.finalize_memory(folder.as_posix())

    assert ok is False
    assert "invalid playbook" in result["message"]
    mocked.assert_not_called()


def test_finalize_still_accepts_legacy_prose(tmp_path):
    folder = _node(tmp_path)
    with patch("tree.mark_processed", return_value=True):
        ok, result = memfinalize.finalize_memory(folder.as_posix())

    assert ok is True
    assert result["playbook"]["reflection"]["legacy"] is True


def test_finalize_freshness_check_runs_before_normalization(tmp_path):
    folder = _node(tmp_path)
    stale = time.time() - 600
    for name in ("memory.md", "reflection.md"):
        target = folder / name
        target.write_text("old", encoding="utf-8")
        target.touch()
        import os

        os.utime(target, (stale, stale))

    with patch("tree.mark_processed", return_value=True) as mocked:
        ok, result = memfinalize.finalize_memory(
            folder.as_posix(), started_at=time.time()
        )

    assert ok is False
    assert "no output written since synthesis started" in result["message"]
    mocked.assert_not_called()
