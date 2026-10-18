from __future__ import annotations

from pathlib import Path
from typing import Any

from server.models.workspace import WorkspaceModel
from runtime.assistant_scope import AssistantScopeMixin


class Workspace(AssistantScopeMixin):
    """Runtime wrapper around a WorkspaceModel instance."""

    #: Singular internal assistant managing ONE workspace.
    ASSISTANT = "workspace_assistant"

    def __init__(self, workspace_model: WorkspaceModel) -> None:
        self.model = workspace_model

    @property
    def pk(self) -> Any:
        """Return the workspace primary key."""
        return self.model.pk

    @property
    def name(self) -> str:
        """Return the workspace name."""
        return self.model.name or ""

    @property
    def description(self) -> str:
        """Return the workspace description."""
        return self.model.description or ""

    @property
    def path(self) -> str:
        """Return the workspace filesystem path."""
        return self.model.path or ""

    @property
    def project(self) -> Any | None:
        """Return the owning project, or *None* (global workspace)."""
        try:
            return self.model.parent_project
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def get_source_dir(self) -> Path:
        """Return the workspace's manifest directory (stored, else path)."""
        from runtime.paths import model_manifest_dir

        return model_manifest_dir(self.model, "workspace")

    # ------------------------------------------------------------------
    # Child collections
    # ------------------------------------------------------------------

    def get_cronjobs_runtime(self) -> Any:
        """Return the cron jobs bound to this workspace (strict)."""
        from runtime.cron.crons import Cronjobs

        return Cronjobs(parent_workspace=self.model)

    def get_skills_runtime(self) -> Any:
        """Return the skills visible in this workspace's project scope."""
        from runtime.skill.skills import Skills

        return Skills(parent_workspace=self.model)

    def get_agents_runtime(self) -> Any:
        """Return the agents visible in this workspace's project scope."""
        from runtime.agents.agents import Agents

        return Agents(parent_workspace=self.model)

    # ------------------------------------------------------------------
    # Assistant wiring
    # ------------------------------------------------------------------

    def assistant_scope_label(self) -> str:
        """Return this workspace's name (or path basename) for the title."""
        if self.name:
            return self.name
        path = self.path.rstrip("/")
        return path.rsplit("/", 1)[-1] if path else "global"

    def get_assistant_workspace(self) -> Any:
        """Return the workspace row binding this workspace's assistant sessions.

        The workspace itself. Shared by ``get_assistant_session`` and UI
        panels so both bind the same row.
        """
        return self.model
