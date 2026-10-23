"""Tests for runtime.memory.paths helpers (pure functions, no DB)."""

import os
import tempfile
from pathlib import Path

from django.test import TestCase

from runtime.memory import paths as mempaths
from server.models.project import Project
from server.models.workspace import WorkspaceModel


def test_memory_root_global():
    with tempfile.TemporaryDirectory() as td:
        import os
        os.environ["AGENTONE_HOME"] = td
        # reset cached? paths reads env each call
        root = mempaths.memory_root()
        assert root == Path(td) / "memory"
        del os.environ["AGENTONE_HOME"]


def test_agent_task_session_dirs():
    root = Path("/tmp/x/memory")
    a = mempaths.agent_memory_dir(root, 42)
    assert a == root / "agents" / "42"
    t = mempaths.task_memory_dir(a, "wiki:timeline")
    assert t == a / "tasks" / "task_wiki:timeline"
    s = mempaths.session_memory_dir(t, 7)
    assert s == t / "sessions" / "7"


def test_write_read_text():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "sub" / "f.md"
        mempaths.write_text(p, "hello")
        assert p.read_text() == "hello"
        assert mempaths.read_text(p) == "hello"
        assert mempaths.read_text(Path(td) / "nope.md") == ""


def test_task_group_default():
    root = Path("/tmp/x/memory")
    a = mempaths.agent_memory_dir(root, 1)
    t = mempaths.task_memory_dir(a, None)
    assert t.name == "task_default"
    t2 = mempaths.task_memory_dir(a, "")
    assert t2.name == "task_default"


def test_newest_mtime_empty():
    with tempfile.TemporaryDirectory() as td:
        assert mempaths.newest_mtime(Path(td)) == 0.0


class WorkspaceMemoryRootTest(TestCase):
    """Legacy blank ``agentone_dir`` rows still resolve to their workspace dir."""

    def _blank_agentone_dir(self, workspace):
        WorkspaceModel.objects.filter(pk=workspace.pk).update(agentone_dir="")
        workspace.refresh_from_db()

    def test_owned_workspace_uses_project_workspace_dir(self):
        project = Project.objects.create(
            name="proj", agentone_dir="/tmp/proj-agentone"
        )
        workspace = WorkspaceModel.objects.create(
            name="PYHTMLGUI", path="/tmp/code", parent_project=project
        )
        self._blank_agentone_dir(workspace)

        self.assertEqual(
            mempaths.memory_root(workspace=workspace),
            Path("/tmp/proj-agentone/workspaces/PYHTMLGUI/memory"),
        )

    def test_unowned_workspace_uses_user_workspace_dir(self):
        with tempfile.TemporaryDirectory() as home:
            with self.settings():
                os.environ["AGENTONE_HOME"] = home
                try:
                    workspace = WorkspaceModel.objects.create(
                        name="PYHTMLGUI", path="/tmp/code"
                    )
                    self._blank_agentone_dir(workspace)
                    self.assertEqual(
                        mempaths.memory_root(workspace=workspace),
                        Path(home) / "workspaces" / "PYHTMLGUI" / "memory",
                    )
                finally:
                    del os.environ["AGENTONE_HOME"]
