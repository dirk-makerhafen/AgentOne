"""Tests for the project primary-workspace picker helpers.

Covers option building and selection resolution, with the key regression
that choosing a folder path which already has a workspace must reuse that
row instead of creating a duplicate.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from django.test import TestCase

from server.models.project import Project
from server.models.workspace import WorkspaceModel
from ui.main.project.workspace_binding import (
    resolve_primary_workspace,
    workspace_options,
)


class TestWorkspaceOptions(TestCase):
    def test_lists_workspaces_with_pk_values(self):
        ws = WorkspaceModel.objects.create(name="Alpha", path="/tmp/alpha")
        opts = workspace_options()
        values = {o["value"] for o in opts}
        assert str(ws.pk) in values
        labels = {o["value"]: o["label"] for o in opts}
        assert "Alpha" in labels[str(ws.pk)]

    def test_project_owned_listed_first(self):
        proj = Project.objects.create(name="proj")
        mine = WorkspaceModel.objects.create(
            name="zzz-mine", path="/tmp/mine", parent_project=proj,
        )
        WorkspaceModel.objects.create(name="aaa-other", path="/tmp/other")
        opts = workspace_options(project=proj)
        assert opts[0]["value"] == str(mine.pk)


class TestResolvePrimaryWorkspace(TestCase):
    def _proj(self, name="proj"):
        return Project.objects.create(name=name)

    def test_empty_ref_returns_none(self):
        ws, err = resolve_primary_workspace("", "", self._proj(), "proj")
        assert ws is None and err is None

    def test_existing_pk_is_selected_and_adopted(self):
        proj = self._proj()
        ws = WorkspaceModel.objects.create(name="Existing", path="/tmp/existing")
        assert ws.parent_project_id is None
        resolved, err = resolve_primary_workspace(str(ws.pk), "", proj, "proj")
        assert err is None and resolved.pk == ws.pk
        ws.refresh_from_db()
        assert ws.parent_project_id == proj.pk

    def test_new_path_reuses_existing_workspace(self):
        proj = self._proj()
        with tempfile.TemporaryDirectory() as d:
            existing = WorkspaceModel.objects.create(name="Pre", path=d)
            count = WorkspaceModel.objects.count()
            resolved, err = resolve_primary_workspace("new", d, proj, "proj")
            assert err is None
            assert resolved.pk == existing.pk
            assert WorkspaceModel.objects.count() == count

    def test_new_path_creates_workspace_and_folder(self):
        proj = self._proj()
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "sub" / "folder"
            resolved, err = resolve_primary_workspace(
                "new", str(target), proj, "proj",
            )
            assert err is None
            assert resolved.path == target.as_posix()
            assert resolved.name == "proj project root"
            assert resolved.parent_project_id == proj.pk
            assert target.is_dir()

    def test_new_without_path_is_error(self):
        ws, err = resolve_primary_workspace("new", "  ", self._proj(), "proj")
        assert ws is None and "path" in err.lower()

    def test_unknown_pk_is_error(self):
        ws, err = resolve_primary_workspace("999999", "", self._proj(), "proj")
        assert ws is None and err is not None

    def test_non_numeric_ref_is_error(self):
        ws, err = resolve_primary_workspace("abc", "", self._proj(), "proj")
        assert ws is None and err is not None
