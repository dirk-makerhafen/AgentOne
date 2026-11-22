from __future__ import annotations

from pathlib import Path
from typing import Any

from server.models.cron import Cronjob
from runtime.assistant_scope import AssistantScopeMixin


class Cron(AssistantScopeMixin):
    """Runtime wrapper around a Cronjob model instance."""

    #: Singular internal assistant working on ONE cron job.
    ASSISTANT = "AgentOne"

    def __init__(self, cronjob_model: Cronjob) -> None:
        self.model = cronjob_model

    @property
    def pk(self) -> Any:
        """Return the cron job primary key."""
        return self.model.pk

    @property
    def name(self) -> str:
        """Return the cron job name."""
        return self.model.name or ""

    @property
    def schedule(self) -> str:
        """Return the cron schedule expression."""
        return self.model.schedule or ""

    @property
    def is_active(self) -> bool:
        """Return whether the cron job is active."""
        return bool(self.model.is_active)

    @property
    def project(self) -> Any | None:
        """Return the owning project, or *None* (global cron job)."""
        try:
            return self.model.parent_project
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def get_source_dir(self) -> Path:
        """Return the source directory anchoring this job's scope (no I/O).

        Cron jobs are DB-canonical (no manifest files). The directory is
        the owning project's manifest dir, or the global AgentOne root.
        """
        project = self.project
        if project is not None:
            try:
                return project.get_agentone_dir()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            p = getattr(project, "path", None)
            if p:
                return Path(p) / ".agentone"
        from django.conf import settings

        return Path(settings.AGENTONE_ROOT)

    def refresh_from_disk(self, details=None):
        """Reload this cron job from disk."""
        self.model.refresh_from_disk(details=details)
        self.model.refresh_from_db()
        return details

    # ------------------------------------------------------------------
    # Assistant wiring
    # ------------------------------------------------------------------

    def assistant_scope_label(self) -> str:
        """Return this cron job's name for the assistant session title."""
        return self.name or "global"

    def get_assistant_workspace(self) -> Any:
        """Return the workspace row binding this job's assistant sessions.

        Same rule as every AgentOne chat: the owning project's primary
        workspace, else AgentOne home.
        """
        from runtime.workspace.workspaces import Workspaces

        return Workspaces.assistant_workspace(project=self.project)
