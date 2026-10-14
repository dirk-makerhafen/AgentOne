from __future__ import annotations

from pathlib import Path
from typing import Any

from django.db.models import QuerySet

from server.models.workspace import WorkspaceModel


class Workspaces:
    """Query interface for WorkspaceModel instances.

    Scoping is explicit: ``parent_project`` limits rows to that project's
    workspaces; ``parent_workspace`` limits rows to workspaces strictly
    inside its directory (sub-workspaces are path-nested, no FK); both
    *None* means all rows.
    """

    #: Collection domain label (used for the global system workspace name).
    DOMAIN = "workspaces"
    #: Internal assistant pair managing workspaces (singular, plural).
    ASSISTANT_NAMES = ("workspace_assistant", "workspaces_assistant")

    def __init__(
        self,
        parent_project: Any = None,
        parent_workspace: Any = None,
    ) -> None:
        self.parent_project = parent_project
        self.parent_workspace = parent_workspace

    @property
    def project(self) -> Any | None:
        """Return the scope project (unwrapping a parent workspace)."""
        if self.parent_project is not None:
            return self.parent_project
        try:
            return getattr(self.parent_workspace, "parent_project", None)
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def all(self) -> QuerySet[WorkspaceModel]:
        """Return workspaces in scope, ordered by name."""
        qs = WorkspaceModel.objects.all()
        if self.parent_workspace is not None:
            try:
                base = Path(self.parent_workspace.path).as_posix().rstrip("/") + "/"
            except Exception:  # pylint: disable=broad-exception-caught
                return qs.none()
            return qs.exclude(path=self.parent_workspace.path).filter(
                path__startswith=base
            ).order_by("name")
        project = self.project
        if project is not None:
            qs = qs.filter(parent_project=project)
        return qs.order_by("name")

    def root(self) -> QuerySet[WorkspaceModel]:
        """Return all workspaces (unscoped; UI + legacy callers)."""
        return WorkspaceModel.objects.filter()

    def list_workspaces(self) -> list:
        """Return workspaces in scope as wrapped :class:`Workspace` objects."""
        from runtime.workspace.workspace import Workspace

        return [Workspace(model) for model in self.all()]

    @staticmethod
    def ensure_named(name: str, path: str | Path, description: str = "") -> WorkspaceModel:
        """Get-or-create a workspace row for an absolute *path* (idempotent)."""
        wanted = Path(path).expanduser().as_posix()
        workspace, _ = WorkspaceModel.objects.update_or_create(
            name=name,
            defaults={"path": wanted, "description": description},
        )
        return workspace

    @staticmethod
    def for_project(project: Any) -> WorkspaceModel:
        """Return the workspace row anchoring a project scope.

        The project's main workspace when set, else the shared
        ``"<root> project root"`` row (same convention as the project
        collection tools, so rows are shared, not duplicated).
        """
        try:
            main_ws = getattr(project, "main_workspace", None)
            if main_ws is not None:
                return main_ws
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        from runtime.paths import project_manifest_dir

        root = project_manifest_dir(project)
        root.mkdir(parents=True, exist_ok=True)
        return Workspaces.ensure_named(
            f"{root.as_posix()} project root",
            root,
            "project root directory",
        )

    # ------------------------------------------------------------------
    # Assistant wiring
    # ------------------------------------------------------------------

    @property
    def assistant_name(self) -> str:
        """Return the collection assistant managing this scope."""
        return self.ASSISTANT_NAMES[1]

    def get_source_dir(self) -> Path:
        """Return the source directory anchoring this scope (no I/O).

        The parent workspace itself, else the scope project's manifest
        directory, else the framework home.
        """
        if self.parent_workspace is not None:
            try:
                from runtime.paths import model_manifest_dir

                return model_manifest_dir(
                    self.parent_workspace, "workspace"
                )
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        project = self.project
        if project is not None:
            from runtime.paths import project_manifest_dir

            return project_manifest_dir(project)
        from runtime.paths import agentone_home

        return agentone_home()

    def get_assistant_session(self, caller: Any = None, name: str | None = None) -> Any | None:
        """Return the singleton workspaces-assistant session for this scope."""
        from runtime.session.sessions import Sessions

        source = self.get_source_dir()
        project = self.project
        if self.parent_workspace is not None:
            workspace = self.parent_workspace
        elif project is not None:
            workspace = self.for_project(project)
        else:
            workspace = self.ensure_named(
                "AgentOne system", source, "Master workspace: whole framework home"
            )
        return Sessions().assistant_session(
            name or self.assistant_name,
            project=project,
            workspace=workspace,
            caller=caller,
        )
