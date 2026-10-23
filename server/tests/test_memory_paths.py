"""Tests for runtime.memory.paths helpers (pure functions, no DB)."""

import tempfile
from pathlib import Path

from runtime.memory import paths as mempaths


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
