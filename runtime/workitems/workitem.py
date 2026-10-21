from __future__ import annotations

from pathlib import Path
from typing import Any

from server.models.workitems.work_item import WorkItem as WorkItemModel
from runtime.assistant_scope import AssistantScopeMixin


class WorkItem(AssistantScopeMixin):
    """Runtime wrapper around a WorkItem model instance.

    Work items have no manifest file; the source directory is the scope
    root (owning project's manifest, else the framework home).
    """

    #: Singular internal assistant working on ONE work item.
    ASSISTANT = "workitem_assistant"

    def __init__(self, work_item_model: WorkItemModel) -> None:
        self.model = work_item_model

    @property
    def pk(self) -> Any:
        """Return the work item primary key."""
        return self.model.pk

    @property
    def title(self) -> str:
        """Return the work item title."""
        return self.model.title or ""

    @property
    def status(self) -> str:
        """Return the work item status."""
        return self.model.status or ""

    @property
    def priority(self) -> int:
        """Return the work item priority (0 = most urgent)."""
        return self.model.priority

    @property
    def project(self) -> Any | None:
        """Return the owning project, or *None* (global inbox item)."""
        try:
            return self.model.project
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def get_source_dir(self) -> Path:
        """Return the scope root for this item (no I/O)."""
        project = self.project
        if project is not None:
            return project.get_agentone_dir()
        from runtime.paths import agentone_home

        return agentone_home()

    def summarise(self, include_body: bool = False) -> dict[str, Any]:
        """Return the model's summary dict, with or without the body."""
        try:
            if include_body:
                return self.model.summarise_with_body()
            return self.model.summarise()
        except Exception:  # pylint: disable=broad-exception-caught
            return {"id": getattr(self.model, "pk", None), "title": self.title}

    # ------------------------------------------------------------------
    # Assistant wiring
    # ------------------------------------------------------------------

    def assistant_scope_label(self) -> str:
        """Return a ``#<id> <title>`` label for the assistant session title."""
        return f"#{self.pk} {self.title}".strip()

    def get_assistant_workspace(self) -> Any:
        """Return the workspace row binding this item's assistant sessions.

        Project scope: project workspace; global inbox: system row.
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
