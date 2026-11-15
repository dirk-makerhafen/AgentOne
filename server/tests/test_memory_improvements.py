"""Tests for the memory improvement queue tool."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from django.test import TestCase

from server.tests.memory_test_support import improvements as memimprovements
from server.tests.memory_test_support import playbook as memplaybook


class _FakeScope:
    def __init__(self, name: str, agentone_dir: Path) -> None:
        self.name = name
        self.pk = 1
        self.parent_project = None
        self.agentone_dir = agentone_dir.as_posix()

    def get_agentone_dir(self) -> Path:
        return Path(self.agentone_dir)


class _FakeSession:
    def __init__(self, root: Path) -> None:
        self.workspace = _FakeScope("ws", root)

    def get_project(self):
        return None


def _write_improvements(root: Path) -> Path:
    import yaml

    path = root / "memory" / "reflection-root" / "improvements.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": memplaybook.IMPROVEMENTS_SCHEMA,
        "proposals": [
            {
                "id": "IMP-1",
                "fingerprint": "harness-settings-override",
                "kind": "harness",
                "scope": "global",
                "status": "candidate",
                "summary": "Fix the transient settings override.",
                "detail": "spawn_subagent nests settings_overrides.",
                "acceptance": "No workaround rule remains.",
            },
            {
                "id": "IMP-2",
                "fingerprint": "prompt-wording",
                "kind": "prompt",
                "scope": "agent",
                "status": "candidate",
                "summary": "Reword the retry instruction.",
            },
        ],
    }
    path.write_text(
        "---\n" + yaml.safe_dump(payload, sort_keys=False) + "---\n",
        encoding="utf-8",
    )
    return path


class MemoryImprovementsToolTest(TestCase):
    def setUp(self):
        import tempfile

        from runtime import memory_playbook

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

        self._old_user_root = memory_playbook._user_memory_root
        memory_playbook._user_memory_root = lambda: self.root / "global-memory"
        self.addCleanup(
            setattr, memory_playbook, "_user_memory_root", self._old_user_root
        )

        _write_improvements(self.root)
        self.session = _FakeSession(self.root)

    def test_list_returns_proposals_without_writing(self):
        from server.models.workitems.work_item import WorkItem

        ok, result = memimprovements.memory_improvements(self.session)

        assert ok is True
        assert result["count"] == 2
        assert {p["id"] for p in result["proposals"]} == {"IMP-1", "IMP-2"}
        assert WorkItem.objects.count() == 0

    def test_same_proposal_at_two_scopes_is_listed_once(self):
        import yaml

        global_file = (
            self.root / "global-memory" / "agents" / "34" / "improvements.md"
        )
        global_file.parent.mkdir(parents=True, exist_ok=True)
        global_file.write_text(
            "---\n"
            + yaml.safe_dump(
                {
                    "schema": memplaybook.IMPROVEMENTS_SCHEMA,
                    "proposals": [
                        {
                            "id": "IMP-1",
                            "fingerprint": "harness-settings-override",
                            "kind": "harness",
                            "summary": "Fix the transient settings override.",
                        }
                    ],
                },
                sort_keys=False,
            )
            + "---\n",
            encoding="utf-8",
        )

        ok, result = memimprovements.memory_improvements(self.session)

        assert ok is True
        matches = [
            item
            for item in result["proposals"]
            if item["fingerprint"] == "harness-settings-override"
        ]
        assert len(matches) == 1
        assert matches[0]["source"] == "workspace ws"

    def test_queue_files_proposals_as_backlog(self):
        from server.models.workitems.enums import WorkItemStatus
        from server.models.workitems.work_item import WorkItem

        ok, result = memimprovements.memory_improvements(
            self.session, action="queue"
        )

        assert ok is True
        assert {item["id"] for item in result["created"]} == {"IMP-1", "IMP-2"}
        assert WorkItem.objects.count() == 2

        item = WorkItem.objects.get(title__startswith="[self-improvement/harness]")
        assert item.status == WorkItemStatus.BACKLOG
        assert "harness-settings-override" in item.body
        assert "No workaround rule remains." in item.body

    def test_queue_is_idempotent(self):
        from server.models.workitems.work_item import WorkItem

        memimprovements.memory_improvements(self.session, action="queue")
        ok, second = memimprovements.memory_improvements(
            self.session, action="queue"
        )

        assert ok is True
        assert second["created"] == []
        assert second["skipped"][0]["reason"] == "already queued"
        assert WorkItem.objects.count() == 2

    def test_queue_can_filter_by_kind(self):
        ok, result = memimprovements.memory_improvements(
            self.session, action="queue", kinds=["prompt"]
        )

        assert ok is True
        assert [item["id"] for item in result["created"]] == ["IMP-2"]
        assert "skipped" in result and not any(
            item["id"] == "IMP-1" for item in result["created"]
        )

    def test_unknown_action_is_refused(self):
        ok, result = memimprovements.memory_improvements(
            self.session, action="apply"
        )

        assert ok is False
        assert "action must be" in result["error"]
