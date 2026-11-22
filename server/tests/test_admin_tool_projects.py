"""DB-backed checks for admin_tool's ported project creation."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / ".agentone" / "agents" / "agentone" / "scripts"),
)

from admin_projects import _projects  # noqa: E402
from admin_workspaces import _workspaces  # noqa: E402
from server.models.project import Project  # noqa: E402
from server.models.workspace import WorkspaceModel  # noqa: E402


class StubSession:
    """Global-scope stand-in — project create does not need a real session."""

    def get_project(self):
        return None

    @property
    def workspace(self):
        return None


def test_create_with_path_links_a_primary_workspace(db, tmp_path):
    root = tmp_path / "demo"

    ok, result = _projects(StubSession(), "create", {"name": "demo", "path": str(root)})

    assert ok, result
    project = Project.objects.get(name="demo")
    assert project.main_workspace is not None
    assert project.path == root.resolve().as_posix()
    assert project.agentone_dir == (root / ".agentone").as_posix()
    assert (root / ".agentone").is_dir()
    assert WorkspaceModel.objects.filter(path=root.resolve().as_posix()).count() == 1


def test_create_without_path_uses_central_manifest(db, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "runtime.paths.central_project_dir", lambda name: tmp_path / "central" / name,
    )

    ok, result = _projects(StubSession(), "create", {"name": "central-demo"})

    assert ok, result
    project = Project.objects.get(name="central-demo")
    assert project.main_workspace is None
    assert project.agentone_dir == (tmp_path / "central" / "central-demo").as_posix()


def test_details_accepts_explicit_project_name(db):
    """A global session can target a named project without auto-scoping."""
    project = Project.objects.create(name="explicit-demo")

    ok, result = _projects(StubSession(), "details", {"project_name": "explicit-demo"})

    assert ok, result
    assert result["project"]["pk"] == project.pk


def test_workspace_details_accepts_explicit_name_outside_scope(db, tmp_path):
    """Explicit identifiers win over the session's inferred workspace."""
    workspace = WorkspaceModel.objects.create(
        name="explicit-ws", path=str(tmp_path / "explicit"),
    )

    ok, result = _workspaces(StubSession(), "details", {"workspace_name": "explicit-ws"})

    assert ok, result
    assert result["workspace"]["pk"] == workspace.pk
