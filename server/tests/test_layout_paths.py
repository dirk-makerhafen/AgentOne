"""Tests for the var/ layout: ScopeRef, path helpers, install repos, migration."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from registry.install_repo import InstallRepo
from runtime import paths
from runtime.session_folder import session_dir
from server.models.project import Project


def _fake_project(name: str, manifest_dir: Path, pk: int = 7):
    return SimpleNamespace(
        name=name,
        pk=pk,
        get_agentone_dir=lambda: manifest_dir,
    )


class HomeLayoutTest(SimpleTestCase):
    def test_bases_live_under_var(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"AGENTONE_HOME": td}):
                home = Path(td)
                self.assertEqual(paths.var_base(), home / "var")
                self.assertEqual(paths.secrets_dir(), home / "secrets")
                self.assertEqual(paths.install_base(), home / "var" / "install")
                self.assertEqual(paths.runtime_base(), home / "var" / "cache" / "runtime")
                self.assertEqual(paths.upstream_base(), home / "var" / "cache" / "upstream")
                self.assertEqual(paths.staging_base(), home / "var" / "cache" / "staging")
                self.assertEqual(paths.log_base(), home / "var" / "log")
                self.assertEqual(paths.run_base(), home / "var" / "run")
                self.assertEqual(paths.browser_base(), home / "var" / "browser")
                with override_settings(AGENTONE_SESSIONS_DIR=""):
                    self.assertEqual(paths.sessions_base(), home / "var" / "sessions")

    def test_browser_prefers_legacy_until_migrated(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "browser" / "profiles").mkdir(parents=True)
            with mock.patch.dict(os.environ, {"AGENTONE_HOME": td}):
                self.assertEqual(paths.browser_base(), home / "browser")
                (home / "var" / "browser").mkdir(parents=True)
                self.assertEqual(paths.browser_base(), home / "var" / "browser")

    def test_sessions_prefers_legacy_until_migrated(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "sessions" / "agent" / "1").mkdir(parents=True)
            with mock.patch.dict(os.environ, {"AGENTONE_HOME": td}):
                with override_settings(AGENTONE_SESSIONS_DIR=""):
                    self.assertEqual(paths.sessions_base(), home / "sessions")
                    (home / "var" / "sessions").mkdir(parents=True)
                    self.assertEqual(paths.sessions_base(), home / "var" / "sessions")


class ScopeRefTest(SimpleTestCase):
    def test_project_paths_are_self_contained(self):
        with tempfile.TemporaryDirectory() as td:
            md = Path(td) / "project-md"
            with mock.patch.dict(os.environ, {"AGENTONE_HOME": str(Path(td) / "home")}):
                scope = paths.ScopeRef.for_project(_fake_project("p", md))
                self.assertEqual(scope.var_dir(), md / "var")
                self.assertEqual(scope.sessions_dir(), md / "var" / "sessions")
                self.assertEqual(scope.log_dir(), md / "var" / "log")
                self.assertEqual(scope.run_dir(), md / "var" / "run")
                self.assertEqual(scope.runtime_dir(), md / "var" / "cache" / "runtime")
                self.assertEqual(
                    scope.new_install_repo_path(),
                    paths.install_base() / "projects" / "7",
                )

    def test_global_and_user_share_home_var(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.dict(os.environ, {"AGENTONE_HOME": td}):
                home_var = Path(td) / "var"
                self.assertEqual(paths.ScopeRef.global_scope().var_dir(), home_var)
                self.assertEqual(paths.ScopeRef.user_scope().var_dir(), home_var)
                self.assertEqual(
                    paths.ScopeRef.global_scope().install_repo_path(),
                    home_var / "install" / "global",
                )
                self.assertEqual(
                    paths.ScopeRef.user_scope().install_repo_path(),
                    home_var / "install" / "user",
                )

    def test_install_repo_uses_legacy_repo_before_migration(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            legacy = home / "install" / "project_My_Proj"
            legacy.mkdir(parents=True)
            with mock.patch.dict(os.environ, {"AGENTONE_HOME": td}):
                scope = paths.ScopeRef.for_project(
                    _fake_project("My Proj", home / "projects" / "My Proj")
                )
                self.assertEqual(scope.install_repo_path(), legacy)
                self.assertEqual(
                    scope.new_install_repo_path(),
                    home / "var" / "install" / "projects" / "7",
                )


class SessionFolderLayoutTest(SimpleTestCase):
    def test_project_session_lives_in_scope_var(self):
        with tempfile.TemporaryDirectory() as td:
            md = Path(td) / "project-md"
            with override_settings(AGENTONE_SESSIONS_DIR=str(Path(td) / "global-sessions")):
                folder = session_dir(5, project=_fake_project("p", md))
            self.assertEqual(folder, md / "var" / "sessions" / "agent" / "5")

    def test_workspace_session_lives_in_workspace_var(self):
        with tempfile.TemporaryDirectory() as td:
            md = Path(td) / "workspace-md"
            workspace = SimpleNamespace(
                name="ws",
                pk=9,
                get_agentone_dir=lambda: md,
            )
            with override_settings(AGENTONE_SESSIONS_DIR=str(Path(td) / "global-sessions")):
                folder = session_dir(6, workspace=workspace)
            self.assertEqual(folder, md / "var" / "sessions" / "agent" / "6")


class InstallRepoSyncTest(SimpleTestCase):
    def test_sync_keyed_by_pk_and_excludes_scope_data(self):
        if not shutil.which("git"):
            self.skipTest("git required")
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            md = Path(td) / "project-md"
            (md / "agents" / "a").mkdir(parents=True)
            (md / "agents" / "a" / "agent.md").write_text("---\nname: a\n---\n")
            (md / "memory").mkdir()
            (md / "memory" / "memory.md").write_text("durable")
            (md / "var" / "sessions" / "agent" / "1").mkdir(parents=True)
            (md / "var" / "sessions" / "agent" / "1" / "scratch.md").write_text("x")
            (md / ".DS_Store").write_text("junk")

            with mock.patch.dict(os.environ, {"AGENTONE_HOME": str(home)}):
                repo = InstallRepo.for_project(_fake_project("p", md), source_root=md)
                repo.sync()

            self.assertEqual(
                repo.repo_path,
                (home / "var" / "install" / "projects" / "7").resolve(),
            )
            self.assertTrue((repo.repo_path / "agents" / "a" / "agent.md").exists())
            self.assertFalse((repo.repo_path / "memory").exists())
            self.assertFalse((repo.repo_path / "var").exists())
            self.assertFalse((repo.repo_path / ".DS_Store").exists())
            self.assertTrue((repo.repo_path / ".scope.json").exists())
            self.assertTrue(repo.tree_sha(md / "agents" / "a"))


class MigrateLayoutCommandTest(TestCase):
    def test_moves_home_and_scope_data_and_rekeys_install(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            project = Project.objects.create(
                name="MyProj", agentone_dir=str(home / "projects" / "MyProj")
            )
            md = Path(project.get_agentone_dir())
            (md / "sessions" / "agent" / "1").mkdir(parents=True)
            (md / "sessions" / "agent" / "1" / "a.md").write_text("x")
            (md / "agents" / "a").mkdir(parents=True)

            (home / "sessions" / "agent" / "2").mkdir(parents=True)
            (home / "browser" / "profiles" / "p").mkdir(parents=True)
            (home / "runtime" / "3").mkdir(parents=True)
            (home / "terminals").mkdir()
            (home / "django_secret_key").write_text("secret")
            (home / "sleep_guard.pid").write_text("123")
            (home / "install" / "project_MyProj").mkdir(parents=True)
            (home / "install" / "project_MyProj" / "repo.txt").write_text("v")

            with mock.patch.dict(os.environ, {"AGENTONE_HOME": td}):
                call_command("migrate_layout", verbosity=0)

            self.assertTrue((home / "var" / "sessions" / "agent" / "2").is_dir())
            self.assertTrue((home / "var" / "browser" / "profiles" / "p").is_dir())
            self.assertTrue((home / "var" / "cache" / "runtime" / "3").is_dir())
            self.assertTrue((home / "var" / "log" / "terminals").is_dir())
            self.assertTrue((home / "var" / "run" / "sleep_guard.pid").exists())
            self.assertTrue((home / "secrets" / "django_secret_key").exists())
            self.assertFalse((home / "django_secret_key").exists())
            self.assertTrue(
                (home / "var" / "install" / "projects" / str(project.pk) / "repo.txt").exists()
            )
            self.assertTrue((md / "var" / "sessions" / "agent" / "1" / "a.md").exists())
            self.assertFalse((md / "sessions").exists())
            self.assertIn("var/", (md / ".gitignore").read_text())

    def test_dry_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / "sessions" / "agent" / "1").mkdir(parents=True)
            with mock.patch.dict(os.environ, {"AGENTONE_HOME": td}):
                call_command("migrate_layout", dry_run=True, verbosity=0)
            self.assertTrue((home / "sessions" / "agent" / "1").is_dir())
            self.assertFalse((home / "var" / "sessions").exists())
