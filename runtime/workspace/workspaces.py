from __future__ import annotations

from pathlib import Path
from typing import Any

from django.db.models import QuerySet

from runtime.assistant_scope import AssistantScopeMixin
from server.models.workspace import WorkspaceModel

#: The single workspace every global AgentOne assistant session binds to.
AGENTONE_HOME_WORKSPACE = "AgentOne home"
#: Pre-unification name; renamed in place so existing chats keep their binding.
_LEGACY_AGENTONE_HOME_WORKSPACE = "AgentOne system"
AGENTONE_HOME_DESCRIPTION = "AgentOne home: framework and user data"


class Workspaces(AssistantScopeMixin):
    """Query interface for WorkspaceModel instances.

    Scoping is explicit: ``parent_project`` limits rows to that project's
    workspaces; ``parent_workspace`` limits rows to workspaces strictly
    inside its directory (sub-workspaces are path-nested, no FK); both
    *None* means all rows.
    """

    #: Collection domain label (used for the global system workspace name).
    DOMAIN = "workspaces"
    #: Unified assistant name for singular/plural workspace wrappers.
    ASSISTANT_NAMES = ("AgentOne", "AgentOne")

    def __init__(
        self,
        parent_project: Any = None,
        parent_workspace: Any = None,
    ) -> None:
        self.parent_project = parent_project
        self.parent_workspace = parent_workspace

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
    def agentone_home_workspace() -> WorkspaceModel:
        """Return the one workspace bound to ``agentone_home()`` (idempotent).

        Older installs named this row ``AgentOne system``. Rename that row in
        place rather than creating a second one: assistant sessions are
        filtered by their exact workspace, so replacing the row would hide
        every existing rightbar chat.
        """
        from runtime.paths import agentone_home

        home = agentone_home()
        try:
            home.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        wanted = home.as_posix()
        row = WorkspaceModel.objects.filter(name=AGENTONE_HOME_WORKSPACE).first()
        if row is None:
            row = WorkspaceModel.objects.filter(
                name=_LEGACY_AGENTONE_HOME_WORKSPACE
            ).first()
        if row is None:
            return Workspaces.ensure_named(
                AGENTONE_HOME_WORKSPACE, wanted, AGENTONE_HOME_DESCRIPTION
            )
        updates = {}
        if row.name != AGENTONE_HOME_WORKSPACE:
            updates["name"] = AGENTONE_HOME_WORKSPACE
        if row.path != wanted:
            updates["path"] = wanted
        if row.description != AGENTONE_HOME_DESCRIPTION:
            updates["description"] = AGENTONE_HOME_DESCRIPTION
        if updates:
            try:
                row.atomic_update(**updates)
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        return row

    @staticmethod
    def assistant_workspace(project: Any = None, workspace: Any = None) -> Any:
        """Return the workspace an AgentOne assistant session binds to.

        The old design minted a synthetic workspace per collection/entity
        type (``System agents``, ``System skills``, ``System cronjobs``,
        ``*_assistant_scope``). There is now one rule: the explicit workspace
        when the caller is workspace-scoped, else the project's primary
        workspace, else AgentOne home.
        """
        if workspace is not None:
            return workspace
        if project is not None:
            return Workspaces.for_project(project)
        return Workspaces.agentone_home_workspace()

    @staticmethod
    def ensure_named(
        name: str,
        path: str | Path,
        description: str = "",
        parent_project: Any = None,
        agentone_dir: str | Path | None = None,
    ) -> WorkspaceModel:
        """Get-or-create a workspace row for an absolute *path* (idempotent).

        When *parent_project* is given, a newly created row is owned by it
        and an existing unowned row is adopted. Rows already owned by
        another project are left untouched. ``agentone_dir`` can override the
        default manifest location for synthetic source-scope workspaces.

        Read-first: if a row already exists and nothing has drifted, return it
        without writing (avoids a DB UPDATE on every GET).
        """
        wanted = Path(path).expanduser().as_posix()
        existing = WorkspaceModel.objects.filter(name=name).first()

        # Adopt an unowned row when a parent project is given.
        if (
            existing is not None
            and parent_project is not None
            and existing.parent_project_id is None
        ):
            try:
                existing.atomic_update(parent_project=parent_project)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        if agentone_dir is not None:
            manifest_dir = Path(agentone_dir).expanduser()
            old_dir = existing.get_agentone_dir() if existing is not None else None
            if old_dir is None or old_dir.resolve() != manifest_dir.resolve():
                migration = _move_manifest_dir(old_dir, manifest_dir)
                try:
                    if existing is None:
                        workspace = WorkspaceModel.objects.create(
                            name=name,
                            path=wanted,
                            description=description,
                            parent_project=parent_project,
                            agentone_dir=manifest_dir.as_posix(),
                        )
                    else:
                        existing.atomic_update(
                            path=wanted,
                            description=description,
                            agentone_dir=manifest_dir.as_posix(),
                        )
                        workspace = existing
                except Exception:
                    if migration is not None:
                        old_dir, new_dir = migration
                        try:
                            new_dir.rename(old_dir)
                        except OSError as rollback_error:
                            raise RuntimeError(
                                f"Workspace data moved to {new_dir}, but the database "
                                f"update failed and rollback to {old_dir} also failed"
                            ) from rollback_error
                    raise
                return workspace

        # Fast path: row already exists and nothing drifted -> no write.
        if existing is not None:
            updates = {}
            if existing.path != wanted:
                updates["path"] = wanted
            if existing.description != description:
                updates["description"] = description
            if updates:
                try:
                    existing.atomic_update(**updates)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
            return existing

        return WorkspaceModel.objects.create(
            name=name,
            path=wanted,
            description=description,
            parent_project=parent_project,
        )

    @staticmethod
    def ensure_source_scope(
        name: str,
        path: str | Path,
        description: str = "",
        parent_project: Any = None,
    ) -> WorkspaceModel:
        """Get-or-create a source-bound workspace with a readable path layout.

        Its AgentOne data lives below
        ``~/.agentone/workspaces/_assistant_scopes/<source path>/`` rather
        than flattening every slash in the source path into one name.
        """
        source = Path(path).expanduser().absolute()
        relative = source.relative_to(source.anchor)
        from runtime.paths import central_workspaces_base

        agentone_dir = (
            central_workspaces_base()
            / "_assistant_scopes"
            / relative
            / "assistant_scope"
        )
        return Workspaces.ensure_named(
            name,
            source,
            description,
            parent_project=parent_project,
            agentone_dir=agentone_dir,
        )

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
        root = project.get_agentone_dir()
        root.mkdir(parents=True, exist_ok=True)
        return Workspaces.ensure_named(
            f"{root.as_posix()} project root",
            root,
            "project root directory",
            parent_project=project,
        )

    # ------------------------------------------------------------------
    # Assistant wiring
    # ------------------------------------------------------------------

    def get_source_dir(self) -> Path:
        """Return the source directory anchoring this scope (no I/O).

        The parent workspace itself, else the scope project's manifest
        directory, else the framework home.
        """
        if self.parent_workspace is not None:
            try:
                return self.parent_workspace.get_agentone_dir()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        project = self.project
        if project is not None:
            return project.get_agentone_dir()
        from runtime.paths import agentone_home

        return agentone_home()

    def get_assistant_workspace(self) -> Any:
        """Return the workspace row binding this scope's assistant sessions.

        Parent workspace when path-nested, else the project's primary
        workspace, else AgentOne home. Shared by ``get_assistant_session``
        and UI panels so both bind the same row.
        """
        return Workspaces.assistant_workspace(
            project=self.project, workspace=self.parent_workspace
        )


def _move_manifest_dir(
    old_dir: Path | None, new_dir: Path
) -> tuple[Path, Path] | None:
    """Move existing synthetic-workspace data to its new manifest directory."""
    if old_dir is None:
        return None
    old = old_dir.expanduser()
    new = new_dir.expanduser()
    if old.resolve() == new.resolve() or not old.exists():
        return None
    if new.exists():
        raise FileExistsError(
            f"Cannot migrate workspace data from {old} to {new}: "
            "the destination already exists"
        )
    new.parent.mkdir(parents=True, exist_ok=True)
    old.rename(new)
    return old, new
