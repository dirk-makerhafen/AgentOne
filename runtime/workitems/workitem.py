from __future__ import annotations

from pathlib import Path
from typing import Any

from server.models.workitems.work_item import WorkItem as WorkItemModel


class WorkItem:
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
            from runtime.paths import project_manifest_dir

            return project_manifest_dir(project)
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

    def get_assistant_session(self, caller: Any = None, name: str | None = None) -> Any | None:
        """Return the singleton ``workitem_assistant`` session in this scope."""
        from runtime.session.sessions import Sessions
        from runtime.workspace.workspaces import Workspaces

        project = self.project
        if project is not None:
            workspace = Workspaces.for_project(project)
        else:
            workspace = Workspaces.ensure_named(
                "AgentOne system",
                self.get_source_dir(),
                "Master workspace: whole framework home",
            )
        return Sessions().assistant_session(
            name or self.ASSISTANT,
            project=project,
            workspace=workspace,
            caller=caller,
        )
