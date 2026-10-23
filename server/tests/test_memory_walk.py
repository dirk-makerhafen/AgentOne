"""Tests for the memory tree walker and ``.memory_sources.md`` generation."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase

from runtime.memory import git as memgit
from runtime.memory import sources as memsources
from runtime.memory.tree import walk_memory
from server.models.agents.agent import AgentModel
from server.models.project import Project
from server.models.sessions.session import SessionModel
from server.models.sessions.session_version import SessionVersionModel
from server.models.workspace import WorkspaceModel


class MemoryWalkTest(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.global_mem = self.tmp / "global" / "memory"
        self.project_mem = self.tmp / "project" / "memory"
        self.top_mem = self.tmp / "top_ws" / "memory"
        self.nested_mem = self.tmp / "nested_ws" / "memory"
        self.global_ws_mem = self.tmp / "global_ws" / "memory"
        for root in (
            self.global_mem,
            self.project_mem,
            self.top_mem,
            self.nested_mem,
            self.global_ws_mem,
        ):
            root.mkdir(parents=True)

        self.project = Project.objects.create(
            name="walk-project", agentone_dir=(self.tmp / "project").as_posix()
        )
        self.top_ws = WorkspaceModel.objects.create(
            name="top",
            path=(self.tmp / "code" / "top").as_posix(),
            parent_project=self.project,
            agentone_dir=(self.tmp / "top_ws").as_posix(),
        )
        self.nested_ws = WorkspaceModel.objects.create(
            name="nested",
            path=(self.tmp / "code" / "top" / "nested").as_posix(),
            parent_project=self.project,
            agentone_dir=(self.tmp / "nested_ws").as_posix(),
        )
        self.global_ws = WorkspaceModel.objects.create(
            name="global-ws",
            path=(self.tmp / "code" / "other").as_posix(),
            agentone_dir=(self.tmp / "global_ws").as_posix(),
        )

        self.global_agent = AgentModel.objects.create(name="walk-global-agent")
        self.project_agent = AgentModel.objects.create(name="walk-project-agent")
        self.top_agent = AgentModel.objects.create(name="walk-top-agent")
        self.nested_agent = AgentModel.objects.create(name="walk-nested-agent")
        self.global_ws_agent = AgentModel.objects.create(name="walk-global-ws-agent")

        self.global_session = self._make_session(
            "walk-global-session", self.global_agent
        )
        self.project_session = self._make_session(
            "walk-project-session", self.project_agent, project=self.project
        )
        self.top_session = self._make_session(
            "walk-top-session", self.top_agent, project=self.project, workspace=self.top_ws
        )
        self.nested_session = self._make_session(
            "walk-nested-session",
            self.nested_agent,
            project=self.project,
            workspace=self.nested_ws,
        )
        self.global_ws_session = self._make_session(
            "walk-global-ws-session", self.global_ws_agent, workspace=self.global_ws
        )

        self.roots = {
            ("project", self.project.pk): self.project_mem,
            ("workspace", self.top_ws.pk): self.top_mem,
            ("workspace", self.nested_ws.pk): self.nested_mem,
            ("workspace", self.global_ws.pk): self.global_ws_mem,
        }
        missing = self.tmp / "missing"
        fake_root = self._fake_memory_root(missing)
        self.patch = patch("runtime.memory.tree.mempaths.memory_root", side_effect=fake_root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

        self._make_agent(self.global_mem, self.global_agent.pk, self.global_session.pk)
        self._make_agent(self.project_mem, self.project_agent.pk, self.project_session.pk)
        self._make_agent(self.top_mem, self.top_agent.pk, self.top_session.pk)
        self._make_agent(self.nested_mem, self.nested_agent.pk, self.nested_session.pk)
        self._make_agent(
            self.global_ws_mem, self.global_ws_agent.pk, self.global_ws_session.pk
        )

        for root, label in (
            (self.global_mem, "global"),
            (self.project_mem, "project"),
            (self.top_mem, "top"),
            (self.nested_mem, "nested"),
            (self.global_ws_mem, "global ws"),
        ):
            self._write_output(root, label)

    def _make_session(self, name, agent, *, project=None, workspace=None):
        session = SessionModel.objects.create(
            name=name, group_key="default", parent_project=project
        )
        SessionVersionModel.objects.create(
            session=session, agent=agent, workspace=workspace
        )
        return session

    def _fake_memory_root(self, missing: Path):
        def fake(session_or_pk=None, *, workspace=None, project=None):
            if workspace is not None:
                return self.roots.get(
                    ("workspace", workspace.pk), missing / f"ws{workspace.pk}"
                )
            if project is not None:
                return self.roots.get(
                    ("project", project.pk), missing / f"project{project.pk}"
                )
            return self.global_mem

        return fake

    def _make_agent(self, root: Path, agent_pk: int, session_pk: int) -> None:
        agent = root / "agents" / str(agent_pk)
        agent.mkdir(parents=True)
        (agent / "memory.md").write_text(f"agent {agent_pk}", encoding="utf-8")
        task = agent / "tasks" / "task_default"
        task.mkdir(parents=True)
        (task / "memory.md").write_text(f"task {agent_pk}", encoding="utf-8")
        session = task / "sessions" / str(session_pk)
        session.mkdir(parents=True)
        (session / "reflections_20261023-120000_1.md").write_text("r", encoding="utf-8")
        (session / "compaction_20261023-120000_2.md").write_text("c", encoding="utf-8")

    def _write_output(self, root: Path, label: str) -> None:
        (root / "memory.md").write_text(f"{label} memory", encoding="utf-8")
        (root / "reflection.md").write_text(f"{label} reflection", encoding="utf-8")

    def _manifest(self, root: Path) -> dict:
        return memsources.read_sources(root / memsources.SOURCES_FILENAME)

    def _source_paths(self, root: Path) -> set[str]:
        return {source["path"] for source in self._manifest(root)["sources"]}

    def _abs(self, path: Path) -> str:
        return path.resolve().as_posix()

    def test_walk_writes_one_manifest_per_non_session_node(self):
        result = walk_memory(write=True)

        self.assertEqual(result["nodes"], 15)
        self.assertEqual(result["manifests_written"], 15)
        self.assertEqual(result["warnings"], [])

        session_dir = (
            self.global_mem
            / "agents"
            / str(self.global_agent.pk)
            / "tasks"
            / "task_default"
            / "sessions"
            / str(self.global_session.pk)
        )
        task_dir = session_dir.parents[1]
        agent_dir = session_dir.parents[3]

        self.assertTrue((self.global_mem / memsources.SOURCES_FILENAME).is_file())
        self.assertTrue((agent_dir / memsources.SOURCES_FILENAME).is_file())
        self.assertTrue((task_dir / memsources.SOURCES_FILENAME).is_file())
        self.assertFalse((session_dir / memsources.SOURCES_FILENAME).exists())

        task_source = self._manifest(task_dir)["sources"][0]
        self.assertEqual(task_source["path"], "sessions/")
        self.assertTrue(memgit.is_git_hash(task_source["current_hash"]))

    def test_manifest_sources_include_child_scope_outputs(self):
        walk_memory(write=True)

        self.assertEqual(
            self._source_paths(self.global_mem),
            {
                "agents/",
                self._abs(self.project_mem),
                self._abs(self.global_ws_mem),
            },
        )
        self.assertEqual(
            self._source_paths(self.project_mem),
            {"agents/", self._abs(self.top_mem)},
        )
        self.assertEqual(
            self._source_paths(self.top_mem),
            {"agents/", self._abs(self.nested_mem)},
        )
        self.assertEqual(self._source_paths(self.nested_mem), {"agents/"})
        self.assertEqual(self._source_paths(self.global_ws_mem), {"agents/"})

        global_sources = {
            source["path"]: source
            for source in self._manifest(self.global_mem)["sources"]
        }
        project_source = global_sources[self._abs(self.project_mem)]
        self.assertEqual(project_source["kind"], "project")
        self.assertEqual(project_source["pk"], self.project.pk)
        self.assertNotIn("pk", global_sources["agents/"])

        project_sources = {
            source["path"]: source
            for source in self._manifest(self.project_mem)["sources"]
        }
        top_source = project_sources[self._abs(self.top_mem)]
        self.assertEqual(top_source["kind"], "workspace")
        self.assertEqual(top_source["pk"], self.top_ws.pk)

        agent_dir = self.global_mem / "agents" / str(self.global_agent.pk)
        self.assertEqual(self._source_paths(agent_dir), {"tasks/"})

        task_dir = agent_dir / "tasks" / "task_default"
        self.assertEqual(self._source_paths(task_dir), {"sessions/"})

    def test_child_identity_preserves_last_hash_after_path_change(self):
        walk_memory(write=True)

        manifest_path = self.global_mem / memsources.SOURCES_FILENAME
        manifest = self._manifest(self.global_mem)
        old_sources = {source["path"]: source for source in manifest["sources"]}
        project_source = old_sources[self._abs(self.project_mem)]
        last = project_source["current_hash"]
        self.assertTrue(memgit.is_git_hash(last))
        project_source["last_processed_hash"] = last
        manifest.pop("generated_at", None)
        memsources.write_sources(manifest_path, manifest)

        moved = self.tmp / "moved" / "project" / "memory"
        moved.parent.mkdir(parents=True)
        shutil.move(self.project_mem.as_posix(), moved.as_posix())
        self.roots[("project", self.project.pk)] = moved

        walk_memory(write=True)

        new_sources = {
            source["path"]: source
            for source in self._manifest(self.global_mem)["sources"]
        }
        moved_source = new_sources[self._abs(moved)]
        self.assertEqual(moved_source["kind"], "project")
        self.assertEqual(moved_source["pk"], self.project.pk)
        self.assertEqual(moved_source["last_processed_hash"], last)
        self.assertEqual(moved_source["current_hash"], last)
        self.assertEqual(moved_source["hours_since_processed"], 0.0)
        self.assertEqual(moved_source["changed_chars"], 0)

    def test_missing_child_outputs_stay_listed(self):
        for name in ("memory.md", "reflection.md"):
            (self.global_ws_mem / name).unlink()
        walk_memory(write=True)

        sources = {
            source["path"]: source
            for source in self._manifest(self.global_mem)["sources"]
        }
        self.assertIn(self._abs(self.global_ws_mem), sources)
        self.assertIsNone(sources[self._abs(self.global_ws_mem)]["current_hash"])

    def test_task_hash_tracks_session_reports(self):
        walk_memory(write=True)
        task_dir = (
            self.global_mem
            / "agents"
            / str(self.global_agent.pk)
            / "tasks"
            / "task_default"
        )
        before = self._manifest(task_dir)["sources"][0]["current_hash"]

        report = (
            task_dir
            / "sessions"
            / str(self.global_session.pk)
            / "reflections_20261024-120000_10.md"
        )
        report.write_text("new report", encoding="utf-8")
        result = walk_memory(write=True)

        after = self._manifest(task_dir)["sources"][0]["current_hash"]
        self.assertNotEqual(before, after)
        self.assertGreater(result["pending"], 0)

    def test_filesystem_only_agents_are_ignored(self):
        orphan = self.global_mem / "agents" / "999999"
        orphan.mkdir(parents=True)
        (orphan / "memory.md").write_text("stale", encoding="utf-8")

        result = walk_memory(write=True)

        self.assertEqual(result["nodes"], 15)
        self.assertFalse((orphan / memsources.SOURCES_FILENAME).exists())

    def test_db_agents_without_memory_dir_get_no_manifest(self):
        agent = AgentModel.objects.create(name="walk-empty-agent")
        session = self._make_session("walk-empty-session", agent)
        empty_dir = self.global_mem / "agents" / str(agent.pk)
        self.assertFalse(empty_dir.exists())
        self.assertIsNotNone(session.pk)

        result = walk_memory(write=True)

        self.assertEqual(result["nodes"], 15)
        self.assertFalse(empty_dir.exists())

    def test_walk_preserves_last_processed_hash_and_is_idempotent(self):
        walk_memory(write=True)
        manifest_path = self.global_mem / memsources.SOURCES_FILENAME
        manifest = self._manifest(self.global_mem)
        git_hash = manifest["sources"][0]["current_hash"]
        self.assertTrue(memgit.is_git_hash(git_hash))
        manifest["sources"][0]["last_processed_hash"] = git_hash
        manifest.pop("generated_at", None)
        memsources.write_sources(manifest_path, manifest)

        walk_memory(write=True)
        preserved = self._manifest(self.global_mem)["sources"][0]
        self.assertEqual(preserved["last_processed_hash"], git_hash)

        result = walk_memory(write=True)
        self.assertEqual(result["manifests_written"], 0)

    def test_source_git_stats_track_changed_content(self):
        walk_memory(write=True)
        manifest_path = self.global_mem / memsources.SOURCES_FILENAME
        manifest = self._manifest(self.global_mem)
        last = manifest["sources"][0]["current_hash"]
        manifest["sources"][0]["last_processed_hash"] = last
        memsources.write_sources(manifest_path, manifest)

        changed = (
            self.global_mem / "agents" / str(self.global_agent.pk) / "memory.md"
        )
        text = "changed agent memory " * 5
        changed.write_text(text, encoding="utf-8")
        walk_memory(write=True)

        updated = self._manifest(self.global_mem)["sources"][0]
        self.assertNotEqual(updated["current_hash"], last)
        self.assertIsNotNone(updated["hours_since_processed"])
        self.assertEqual(updated["changed_chars"], len(text))

    def test_mark_processed_snapshots_current_hashes(self):
        walk_memory(write=True)
        changed = (
            self.global_mem / "agents" / str(self.global_agent.pk) / "memory.md"
        )
        changed.write_text("new agent memory", encoding="utf-8")

        from runtime.memory.tree import mark_processed

        self.assertTrue(mark_processed(self.global_mem))
        for source in self._manifest(self.global_mem)["sources"]:
            self.assertEqual(
                source["last_processed_hash"], source["current_hash"]
            )
            if source["current_hash"] is None:
                self.assertIsNone(source["hours_since_processed"])
                self.assertIsNone(source["changed_chars"])
            else:
                self.assertEqual(source["hours_since_processed"], 0.0)
                self.assertEqual(source["changed_chars"], 0)

    def test_dry_run_does_not_write_manifests(self):
        manifest_path = self.global_mem / memsources.SOURCES_FILENAME
        result = walk_memory(write=False)
        self.assertFalse(manifest_path.exists())
        self.assertEqual(result["manifests_written"], 0)
        self.assertEqual(result["nodes"], 15)

    def test_scope_gitignore_excludes_manifest(self):
        walk_memory(write=True)
        if not memgit._git_available():  # pylint: disable=protected-access
            self.skipTest("git not available")
        gitignore = (self.global_mem / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".memory_sources.md", gitignore)
