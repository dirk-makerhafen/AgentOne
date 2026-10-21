from __future__ import annotations

from pathlib import Path
from typing import Any

from django.db.models import QuerySet

from runtime.assistant_scope import AssistantScopeMixin
from server.models.workitems.work_item import WorkItem as WorkItemModel


class Workitems(AssistantScopeMixin):
    """Query interface for WorkItem instances.

    Scoping is explicit and strict: ``parent_project`` selects that
    project's items; ``parent_workspace`` unwraps to its project; both
    *None* selects the global inbox (``project__isnull``).

    Ordering (highest priority value first) is baked in, matching the
    model default and the previous assistant behavior.
    """

    #: Collection domain label.
    DOMAIN = "workitems"
    #: Internal assistant pair managing work items (singular, plural).
    ASSISTANT_NAMES = ("workitem_assistant", "workitems_assistant")

    def __init__(
        self,
        parent_project: Any = None,
        parent_workspace: Any = None,
    ) -> None:
        self.parent_project = parent_project
        self.parent_workspace = parent_workspace

    def all(self) -> QuerySet[WorkItemModel]:
        """Return work items in scope, highest priority value first."""
        project = self.project
        qs = WorkItemModel.objects.all()
        if project is not None:
            qs = qs.filter(project=project)
        else:
            qs = qs.filter(project__isnull=True)
        return qs.select_related("assigned_agent", "project").order_by(
            "-priority", "created_at"
        )

    def root(self) -> QuerySet[WorkItemModel]:
        """Return all work items (unscoped)."""
        return WorkItemModel.objects.all()

    def list_workitems(self) -> list:
        """Return work items in scope as wrapped :class:`WorkItem` objects."""
        from runtime.workitems.workitem import WorkItem

        return [WorkItem(model) for model in self.all()]

    # ------------------------------------------------------------------
    # Assistant wiring
    # ------------------------------------------------------------------

    def get_source_dir(self) -> Path:
        """Return the source directory anchoring this scope (no I/O).

        The scope project's manifest directory, the parent workspace's
        manifest (or path), else the framework home (global inbox).
        """
        project = self.project
        if project is not None:
            return project.get_agentone_dir()
        if self.parent_workspace is not None:
            return self.parent_workspace.get_agentone_dir()
        from runtime.paths import agentone_home

        return agentone_home()

    def get_assistant_workspace(self) -> Any:
        """Return the workspace row binding this scope's assistant sessions.

        Project scope: project workspace; global inbox: system row. Shared
        by ``get_assistant_session`` and UI panels so both bind the same row.
        """
        from runtime.workspace.workspaces import Workspaces

        project = self.project
        if project is not None:
            return Workspaces.for_project(project)
        return Workspaces.ensure_named(
            "AgentOne system",
            self.get_source_dir(),
            "Master workspace: whole framework home",
        )
