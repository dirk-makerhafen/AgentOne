"""Tests for workspace manifest-location helpers (inline vs central)."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase

from server.models.workspace import WorkspaceModel
from ui.main.workspace.manifest_location import (
    STORAGE_CENTRAL,
    STORAGE_INLINE,
    STORAGE_NONE,
    central_manifest_dir,
    detect_storage,
    ensure_manifest_dir,
    inline_manifest_dir,
    storage_options,
)


class TestStorageOptions(TestCase):
    def test_has_three_modes(self):
        values = [o["value"] for o in storage_options()]
        assert values == [STORAGE_NONE, STORAGE_INLINE, STORAGE_CENTRAL]


class TestDetectStorage(TestCase):
    def test_blank_manifest_dir_is_none(self):
        ws = WorkspaceModel.objects.create(name="w", path="/tmp/w")
        assert detect_storage(ws) == STORAGE_NONE

    def test_inline_when_manifest_in_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            ws = WorkspaceModel.objects.create(
                name="w", path=d, manifest_dir=str(Path(d) / ".agentone"),
            )
            assert detect_storage(ws) == STORAGE_INLINE

    def test_central_when_under_home(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict("os.environ", {"AGENTONE_HOME": home}):
                ws = WorkspaceModel.objects.create(name="w", path="/tmp/w")
                ws.manifest_dir = str(central_manifest_dir(ws))
                assert detect_storage(ws) == STORAGE_CENTRAL


class TestEnsureManifestDir(TestCase):
    def test_inline_creates_dir_and_gitignore(self):
        with tempfile.TemporaryDirectory() as d:
            ws = WorkspaceModel.objects.create(name="w", path=d)
            out = ensure_manifest_dir(ws, STORAGE_INLINE, d, gitignore=True)
            assert out == inline_manifest_dir(d).as_posix()
            assert (Path(d) / ".agentone").is_dir()
            assert ".agentone/" in (Path(d) / ".gitignore").read_text()

    def test_central_creates_dir_under_home(self):
        with tempfile.TemporaryDirectory() as home:
            with mock.patch.dict("os.environ", {"AGENTONE_HOME": home}):
                ws = WorkspaceModel.objects.create(name="myws", path="/tmp/myws")
                out = ensure_manifest_dir(ws, STORAGE_CENTRAL, "/tmp/myws")
                assert out == str(Path(home) / "workspaces" / "myws")
                assert Path(out).is_dir()

    def test_none_returns_empty(self):
        ws = WorkspaceModel.objects.create(name="w", path="/tmp/w")
        assert ensure_manifest_dir(ws, STORAGE_NONE, "/tmp/w") == ""
