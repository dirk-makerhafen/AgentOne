"""Tests for the layer-aware memory merge dispatcher and its prompts."""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import frontmatter
import pytest

from runtime.memory import finalize as memfinalize
from runtime.memory import git as memgit
from runtime.memory import sources as memsources

REPO_ROOT = Path(__file__).resolve().parents[2]
MEMORY_SCRIPTS = (
    REPO_ROOT
    / ".agentone"
    / "agents"
    / "internal"
    / "memory-manage"
    / "scripts"
)


def _load_module(file_name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, MEMORY_SCRIPTS / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merge = _load_module("memory_merge.py", "agentone_memory_merge_under_test")
finalize = _load_module("memory_finalize.py", "agentone_memory_finalize_under_test")


def _node(
    tmp_path: Path,
    *,
    kind: str,
    memory_type: str,
    key: str = "1",
    name: str = "",
    depth: int = 0,
    sources: list[dict] | None = None,
) -> dict:
    """Create a memory node with a manifest and return a walker-style item."""
    folder = tmp_path / f"{kind}-{key}"
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "kind": kind,
        "type": memory_type,
        "key": key,
        "name": name or key,
        "sources": sources or [
            {
                "path": "sessions/",
                "type": f"{memory_type}-sessions",
                "last_processed_hash": "a" * 40,
                "current_hash": "b" * 40,
                "hours_since_processed": 3.5,
                "changed_chars": 1204,
            }
        ],
    }
    memsources.write_sources(folder / memsources.SOURCES_FILENAME, payload)
    return {
        "manifest_path": (folder / memsources.SOURCES_FILENAME).as_posix(),
        "node_kind": kind,
        "node_key": key,
        "type": memory_type,
        "depth": depth,
        "sources": payload["sources"],
    }


class _FakeCall:
    def __init__(self, pk: int):
        self.pk = pk


class _FakeTask:
    def __init__(self, name: str):
        self.name = name
        self.calls: list[tuple[tuple, dict]] = []

    def delay(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return _FakeCall(pk=900 + len(self.calls))


class _FakeChild:
    def __init__(self, pk: int):
        self.model = SimpleNamespace(pk=pk)
        self.prompts: list[str] = []
        self.call: _FakeCall | None = None

    def add_user_message(self, message):
        self.prompts.append(message)
        self.call = _FakeCall(pk=self.model.pk + 1000)
        return self.call


class _FakeSession:
    def __init__(self):
        self.spawn_calls: list[tuple[str, dict]] = []
        self.children: list[_FakeChild] = []
        self.tasks: dict[str, _FakeTask] = {}

    def spawn_subagent(self, agent, **kwargs):
        child = _FakeChild(pk=100 + len(self.children))
        self.children.append(child)
        self.spawn_calls.append((agent, kwargs))
        return child

    def get_task(self, name: str):
        if name not in self.tasks:
            self.tasks[name] = _FakeTask(name)
        return self.tasks[name]


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "memory_type", "key", "name", "expect_title", "expect_label"),
    [
        ("task", "global-agent-task", "default", "task_default", "Task memory synthesis", "default"),
        ("agent", "project-agent", "1", "reviewer", "Agent memory synthesis", "reviewer"),
        ("global", "global", "global", "global", "Scope memory synthesis", "global"),
        ("project", "project", "3", "Atlas", "Scope memory synthesis", "**Atlas** project scope"),
        ("workspace", "workspace", "4", "repo", "Scope memory synthesis", "**repo** workspace scope"),
    ],
)
def test_build_prompt_covers_every_layer(
    tmp_path, kind, memory_type, key, name, expect_title, expect_label
):
    item = _node(
        tmp_path,
        kind=kind,
        memory_type=memory_type,
        key=key,
        name=name,
    )
    rendered = merge.build_prompt(item)

    assert "{{" not in rendered and "}}" not in rendered
    assert item["manifest_path"].rsplit("/", 1)[0] in rendered
    assert "memory.md" in rendered
    assert "reflection.md" in rendered
    assert "memory_mark_processed" not in rendered
    assert "harness marks this node processed" in rendered
    assert expect_title in rendered
    assert expect_label in rendered


@pytest.mark.parametrize(
    ("kind", "memory_type", "expected"),
    [
        ("task", "global-agent-task", ("task", "global")),
        ("task", "project-agent-task", ("task", "project")),
        ("task", "workspace-agent-task", ("task", "workspace")),
        ("agent", "global-agent", ("agent", "global")),
        ("agent", "project-agent", ("agent", "project")),
        ("agent", "workspace-agent", ("agent", "workspace")),
        ("global", "global", ("scope", "global")),
        ("project", "project", ("scope", "project")),
        ("workspace", "workspace", ("scope", "workspace")),
    ],
)
def test_classify_every_node_type(tmp_path, kind, memory_type, expected):
    item = _node(tmp_path, kind=kind, memory_type=memory_type, key="9")
    manifest = memsources.read_sources(Path(item["manifest_path"]))
    assert merge._classify(item, manifest) == expected


def test_memory_manage_finalizes_programmatically():
    agent_file = (
        REPO_ROOT
        / ".agentone"
        / "agents"
        / "internal"
        / "memory-manage"
        / "agent.md"
    )
    manifest = frontmatter.load(agent_file)

    assert "memory_mark_processed" not in manifest.get("tools", [])
    assert "memory_finalize" in manifest.get("tasks", [])
    # Finalization is chained by memory_merge, not by a session-end hook.
    assert not manifest.get("hooks")


def test_prompt_lists_files_on_first_synthesis(tmp_path):
    item = _node(
        tmp_path,
        kind="task",
        memory_type="workspace-agent-task",
        key="default",
        sources=[
            {
                "path": "sessions/",
                "type": "workspace-agent-task-sessions",
                "last_processed_hash": None,
                "current_hash": "b" * 40,
                "hours_since_processed": None,
                "changed_chars": None,
            }
        ],
    )
    folder = Path(item["manifest_path"]).parent
    session_dir = folder / "sessions" / "12"
    session_dir.mkdir(parents=True)
    (session_dir / "compaction_2026.md").write_text("summary", encoding="utf-8")
    (session_dir / "reflections_2026.md").write_text("lesson", encoding="utf-8")
    (folder / "sessions" / ".memory_sources.md").write_text("meta", encoding="utf-8")

    rendered = merge.build_prompt(item)

    assert (
        "Files: `12/compaction_2026.md`, `12/reflections_2026.md`"
        in rendered
    )
    files_line = next(line for line in rendered.splitlines() if "Files:" in line)
    assert ".memory_sources.md" not in files_line


def test_prompt_lists_only_files_changed_between_hashes(tmp_path):
    folder = tmp_path / "task-git"
    memgit.ensure_repo(folder)
    sessions = folder / "sessions"
    sessions.mkdir()
    (sessions / "old.md").write_text("old fact", encoding="utf-8")
    old = memgit.commit_all(folder, message="old")
    (sessions / "new.md").write_text("new fact", encoding="utf-8")
    new = memgit.commit_all(folder, message="new")

    item = {
        "manifest_path": (folder / memsources.SOURCES_FILENAME).as_posix(),
        "node_kind": "task",
        "node_key": "default",
        "type": "workspace-agent-task",
        "depth": 3,
        "sources": [
            {
                "path": "sessions/",
                "type": "workspace-agent-task-sessions",
                "last_processed_hash": old,
                "current_hash": new,
                "hours_since_processed": 1.0,
                "changed_chars": 8,
            }
        ],
    }
    memsources.write_sources(
        folder / memsources.SOURCES_FILENAME,
        {
            "kind": "task",
            "type": "workspace-agent-task",
            "key": "default",
            "name": "task_default",
            "sources": item["sources"],
        },
    )

    rendered = merge.build_prompt(item)

    assert "Changed files: `new.md`" in rendered
    assert "old.md" not in rendered


def test_prompt_lists_changed_sources_with_stats(tmp_path):
    item = _node(
        tmp_path,
        kind="task",
        memory_type="workspace-agent-task",
        key="default",
        sources=[
            {
                "path": "sessions/",
                "type": "workspace-agent-task-sessions",
                "last_processed_hash": "1234567890" + "a" * 30,
                "current_hash": "abcdef1234" + "b" * 30,
                "hours_since_processed": 2.5,
                "changed_chars": 2500,
            }
        ],
    )
    rendered = merge.build_prompt(item)

    assert "`sessions/`" in rendered
    assert "session reports" in rendered
    assert "2,500 chars changed" in rendered
    assert "2.5h ago" in rendered
    assert "12345678 → abcdef12" in rendered


def test_scope_prompt_mentions_child_scopes(tmp_path):
    item = _node(
        tmp_path,
        kind="project",
        memory_type="project",
        key="3",
        name="Atlas",
        sources=[
            {
                "path": "agents/",
                "type": "project-agents",
                "last_processed_hash": "a" * 40,
                "current_hash": "b" * 40,
                "hours_since_processed": 1.0,
                "changed_chars": 10,
            },
            {
                "path": "/tmp/atlas-workspace/memory",
                "type": "workspace",
                "pk": 4,
                "last_processed_hash": "c" * 40,
                "current_hash": "d" * 40,
                "hours_since_processed": 1.0,
                "changed_chars": 20,
            },
        ],
    )
    rendered = merge.build_prompt(item)

    assert "**Atlas** project scope" in rendered
    assert "child workspace memory" in rendered
    assert "/tmp/atlas-workspace/memory" in rendered


# ---------------------------------------------------------------------------
# Batch selection and dispatch
# ---------------------------------------------------------------------------


def test_select_batch_only_takes_the_deepest_layer(tmp_path):
    task = _node(tmp_path, kind="task", memory_type="global-agent-task", key="t", depth=3)
    agent = _node(tmp_path, kind="agent", memory_type="global-agent", key="a", depth=2)
    scope = _node(tmp_path, kind="global", memory_type="global", key="g", depth=0)

    batch = merge._select_batch([scope, agent, task], 0)

    assert batch == [task]


def test_select_batch_limits_dispatch(tmp_path):
    items = [
        _node(tmp_path, kind="task", memory_type="global-agent-task", key=str(i), depth=3)
        for i in range(3)
    ]

    assert len(merge._select_batch(items, 2)) == 2


def test_memory_merge_spawns_synthesizers_and_leaves_manifests_alone(tmp_path):
    task = _node(tmp_path, kind="task", memory_type="project-agent-task", key="default", depth=3)
    agent = _node(tmp_path, kind="agent", memory_type="project-agent", key="7", depth=2)
    before = Path(task["manifest_path"]).read_text(encoding="utf-8")

    session = _FakeSession()
    ok, result = merge.merge_items(session, [agent, task])

    assert ok is True
    assert result["layer"] == "task"
    assert len(result["dispatched"]) == 1
    assert result["remaining"] == 1
    # Only the task layer was dispatched; the agent waits for the next pass.
    assert len(session.children) == 1
    assert session.spawn_calls[0][0] == "memory-manage"
    assert session.spawn_calls[0][1]["allow_internal"] is True
    assert session.spawn_calls[0][1]["session_type"] == "subtask_delegate"
    assert "settings_overrides" not in session.spawn_calls[0][1]
    child = session.children[0]
    prompt = child.prompts[0]
    assert "Task memory synthesis" in prompt
    assert Path(task["manifest_path"]).parent.as_posix() in prompt
    # The child's task call is chained into memory_finalize, so the framework
    # auto-awaits the synthesizer and hands its result to finalization.
    assert len(session.tasks["memory_finalize"].calls) == 1
    args, kwargs = session.tasks["memory_finalize"].calls[0]
    assert args == (child.call,)
    assert kwargs["target_dir"] == Path(task["manifest_path"]).parent.resolve().as_posix()
    assert kwargs["started_at"] > 0
    assert result["dispatched"][0]["finalize_call_pk"] == 901
    # The manifest is advanced by memory_finalize, never by the dispatcher.
    assert Path(task["manifest_path"]).read_text(encoding="utf-8") == before


def test_memory_merge_with_nothing_pending_is_a_no_op():
    session = _FakeSession()
    ok, result = merge.merge_items(session, [])

    assert ok is True
    assert result["dispatched"] == []
    assert session.children == []


def test_memory_merge_walks_then_dispatches(tmp_path, monkeypatch):
    task = _node(tmp_path, kind="task", memory_type="global-agent-task", key="t", depth=3)
    monkeypatch.setattr(merge, "_walk_pending", lambda: [task])

    session = _FakeSession()
    ok, result = merge.memory_merge(session)

    assert ok is True
    assert result["layer"] == "task"
    assert len(session.children) == 1


def test_memory_merge_reports_walk_failure(monkeypatch):
    def _boom():
        raise RuntimeError("walk exploded")

    monkeypatch.setattr(merge, "_walk_pending", _boom)

    ok, result = merge.memory_merge(_FakeSession())

    assert ok is False
    assert result["message"] == "walk exploded"


def test_memory_merge_reports_spawn_failure(tmp_path):
    task = _node(tmp_path, kind="task", memory_type="global-agent-task", key="t", depth=3)

    class BrokenSession(_FakeSession):
        def spawn_subagent(self, *args, **kwargs):
            return None

    ok, result = merge.merge_items(BrokenSession(), [task])

    assert ok is False
    assert result["status"] == "error"
    assert result["failed"][0]["error"] == "agent 'memory-manage' not found"


def test_memory_merge_requires_the_finalize_task(tmp_path):
    task = _node(tmp_path, kind="task", memory_type="global-agent-task", key="t", depth=3)

    class NoFinalizeSession(_FakeSession):
        def get_task(self, name):
            return None

    session = NoFinalizeSession()
    ok, result = merge.merge_items(session, [task])

    assert ok is False
    assert session.children == []
    assert "memory_finalize" in result["failed"][0]["error"]


def test_memory_merge_reports_unreadable_manifest(tmp_path):
    item = _node(tmp_path, kind="task", memory_type="global-agent-task", key="t", depth=3)
    Path(item["manifest_path"]).unlink()

    ok, result = merge.merge_items(_FakeSession(), [item])

    assert ok is False
    assert "manifest not found" in result["failed"][0]["error"]


def _marker(folder: Path, started_at: float) -> None:
    (folder / ".memory_inflight").write_text(
        json.dumps({"started_at": started_at, "layer": "task"}),
        encoding="utf-8",
    )


def test_merge_skips_a_node_already_in_flight(tmp_path):
    task = _node(tmp_path, kind="task", memory_type="global-agent-task", key="t", depth=3)
    _marker(Path(task["manifest_path"]).parent, time.time())

    session = _FakeSession()
    ok, result = merge.merge_items(session, [task])

    assert ok is True
    assert result["status"] == "busy"
    assert result["skipped"][0]["reason"] == "synthesis already running"
    assert session.children == []


def test_merge_retries_after_a_stale_marker(tmp_path):
    task = _node(tmp_path, kind="task", memory_type="global-agent-task", key="t", depth=3)
    _marker(Path(task["manifest_path"]).parent, time.time() - 7200)

    session = _FakeSession()
    ok, result = merge.merge_items(session, [task])

    assert ok is True
    assert result["dispatched"]
    assert len(session.children) == 1


# ---------------------------------------------------------------------------
# Manifest advancement
# ---------------------------------------------------------------------------


def test_finalize_refuses_without_written_output(tmp_path):
    item = _node(tmp_path, kind="task", memory_type="global-agent-task", key="t")
    folder = Path(item["manifest_path"]).parent

    ok, result = memfinalize.finalize_memory(folder.as_posix())

    assert ok is False
    assert "no memory output" in result["message"]


def test_finalize_refuses_without_manifest(tmp_path):
    folder = tmp_path / "not-a-node"
    folder.mkdir()
    (folder / "memory.md").write_text("x", encoding="utf-8")

    ok, result = memfinalize.finalize_memory(folder.as_posix())

    assert ok is False
    assert "memory_walk" in result["message"]


def test_finalize_advances_the_node(tmp_path):
    item = _node(tmp_path, kind="task", memory_type="global-agent-task", key="t")
    folder = Path(item["manifest_path"]).parent
    (folder / "memory.md").write_text("facts", encoding="utf-8")
    (folder / "reflection.md").write_text("lessons", encoding="utf-8")
    _marker(folder, time.time())

    with patch("runtime.memory.tree.mark_processed", return_value=True) as mocked:
        ok, result = memfinalize.finalize_memory(folder.as_posix())

    assert ok is True
    assert result["files"] == ["memory.md", "reflection.md"]
    assert not (folder / ".memory_inflight").exists()
    mocked.assert_called_once()
    assert Path(mocked.call_args.args[0]).resolve() == folder.resolve()


def test_finalize_refuses_stale_output(tmp_path):
    item = _node(tmp_path, kind="task", memory_type="global-agent-task", key="t")
    folder = Path(item["manifest_path"]).parent
    output = folder / "memory.md"
    output.write_text("old facts", encoding="utf-8")
    stale = time.time() - 600
    os.utime(output, (stale, stale))
    _marker(folder, time.time())

    with patch("runtime.memory.tree.mark_processed", return_value=True) as mocked:
        ok, result = memfinalize.finalize_memory(
            folder.as_posix(), started_at=time.time()
        )

    assert ok is False
    assert "no output written since synthesis started" in result["message"]
    mocked.assert_not_called()


def test_memory_finalize_task_advances_node_and_reports_result(tmp_path):
    item = _node(tmp_path, kind="task", memory_type="global-agent-task", key="t")
    folder = Path(item["manifest_path"]).parent
    (folder / "memory.md").write_text("facts", encoding="utf-8")
    (folder / "reflection.md").write_text("lessons", encoding="utf-8")
    started = time.time()
    _marker(folder, started)

    with patch("runtime.memory.tree.mark_processed", return_value=True) as mocked:
        ok, result = finalize.memory_finalize(
            None,
            "task synthesis done",
            target_dir=folder.as_posix(),
            started_at=started,
        )

    assert ok is True
    assert result["synthesizer_result"] == "task synthesis done"
    assert result["files"] == ["memory.md", "reflection.md"]
    assert not (folder / ".memory_inflight").exists()
    mocked.assert_called_once()
    assert Path(mocked.call_args.args[0]).resolve() == folder.resolve()


def test_memory_finalize_task_requires_a_target():
    ok, result = finalize.memory_finalize(None, "done")

    assert ok is False
    assert "target_dir is required" in result["message"]
