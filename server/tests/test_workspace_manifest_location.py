"""Tests for workspace agentone-directory location helpers."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase

from server.models.project import Project
from server.models.workspace import WorkspaceModel
from ui.main.workspace.manifest_location import (
    STORAGE_CENTRAL,
    STORAGE_INLINE,
    STORAGE_NONE,
    STORAGE_PROJECT,
    STORAGE_USER,
    central_manifest_dir,
    detect_storage,
    ensure_manifest_dir,
    inline_manifest_dir,
    project_workspace_manifest_dir,
    storage_options,
    user_manifest_dir,
)


class TestStorageOptions(TestCase):
    def test_has_three_distinct_modes(self):
        values = [o["value"] for o in storage_options()]
        assert values == [STORAGE_INLINE, STORAGE_PROJECT, STORAGE_USER]


class TestDetectStorage(TestCase):
    def test_blank_manifest_dir_defaults_to_user_without_project(self):
        ws = WorkspaceModel.objects.create(name="w", path="/tmp/w")
        assert detect_storage(ws) == STORAGE_USER

    def test_blank_manifest_dir_defaults_to_project_with_project(self):
        project = Project.objects.create(name="p")
        ws = WorkspaceModel.objects.create(
            name="w", path="/tmp/w", parent_project=project
        )
        assert detect_storage(ws) == STORAGE_PROJECT

    def test_inline_when_manifest_in_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            ws = WorkspaceModel.objects.create(
                name="w", path=d, agentone_dir=str(Path(d) / ".agentone"),
            )
            assert detect_storage(ws) == STORAGE_INLINE

    def test_project_when_under_project_tree(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict("os.environ", {"AGENTONE_HOME": home}):
                project = Project.objects.create(name="p")
                ws = WorkspaceModel.objects.create(
                    name="w", path="/tmp/w", parent_project=project
                )
                ws.agentone_dir = str(project_workspace_manifest_dir(ws))
                assert detect_storage(ws) == STORAGE_PROJECT

    def test_user_when_under_home(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict("os.environ", {"AGENTONE_HOME": home}):
                project = Project.objects.create(name="p")
                ws = WorkspaceModel.objects.create(
                    name="w", path="/tmp/w", parent_project=project
                )
                ws.agentone_dir = str(user_manifest_dir(ws))
                assert detect_storage(ws) == STORAGE_USER

    def test_legacy_central_dir_still_detected(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict("os.environ", {"AGENTONE_HOME": home}):
                project = Project.objects.create(name="p")
                ws = WorkspaceModel.objects.create(
                    name="w", path="/tmp/w", parent_project=project
                )
                ws.agentone_dir = str(central_manifest_dir(ws))
                assert detect_storage(ws) == STORAGE_PROJECT


class TestEnsureManifestDir(TestCase):
    def test_inline_creates_dir_and_gitignore(self):
        with tempfile.TemporaryDirectory() as d:
            ws = WorkspaceModel.objects.create(name="w", path=d)
            out = ensure_manifest_dir(ws, STORAGE_INLINE, d, gitignore=True)
            assert out == inline_manifest_dir(d).as_posix()
            assert (Path(d) / ".agentone").is_dir()
            assert ".agentone/" in (Path(d) / ".gitignore").read_text()

    def test_project_creates_dir_under_project_tree(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict("os.environ", {"AGENTONE_HOME": home}):
                project = Project.objects.create(name="p")
                ws = WorkspaceModel.objects.create(
                    name="myws", path="/tmp/myws", parent_project=project
                )
                out = ensure_manifest_dir(ws, STORAGE_PROJECT, "/tmp/myws")
                assert out == project_workspace_manifest_dir(ws).as_posix()
                assert Path(out).is_dir()

    def test_user_creates_dir_under_home(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict("os.environ", {"AGENTONE_HOME": home}):
                project = Project.objects.create(name="p")
                ws = WorkspaceModel.objects.create(
                    name="myws", path="/tmp/myws", parent_project=project
                )
                out = ensure_manifest_dir(ws, STORAGE_USER, "/tmp/myws")
                assert out == str(Path(home) / "workspaces" / "myws")
                assert Path(out).is_dir()

    def test_central_legacy_creates_under_project_when_owned(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict("os.environ", {"AGENTONE_HOME": home}):
                project = Project.objects.create(name="p")
                ws = WorkspaceModel.objects.create(
                    name="myws", path="/tmp/myws", parent_project=project
                )
                out = ensure_manifest_dir(ws, STORAGE_CENTRAL, "/tmp/myws")
                assert out == project_workspace_manifest_dir(ws).as_posix()

    def test_none_returns_empty(self):
        ws = WorkspaceModel.objects.create(name="w", path="/tmp/w")
        assert ensure_manifest_dir(ws, STORAGE_NONE, "/tmp/w") == ""
