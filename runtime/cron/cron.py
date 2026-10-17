from __future__ import annotations

from pathlib import Path
from typing import Any

from server.models.cron import Cronjob


class Cron:
    """Runtime wrapper around a Cronjob model instance."""

    #: Singular internal assistant working on ONE cron job.
    ASSISTANT = "cronjob_assistant"

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
        """Return the directory holding this job's manifest (no I/O).

        Stored ``manifest_dir`` first; else the canonical cron file
        location from ``runtime.cron.file_io`` (project manifest
        ``cronjobs/`` or the global tree).
        """
        try:
            stored = str(getattr(self.model, "manifest_dir", "") or "").strip()
            if stored:
                import os

                return Path(os.path.expanduser(stored))
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        from runtime.cron.file_io import cron_file_path

        return cron_file_path(self.name or ".scope", self.project).parent

    # ------------------------------------------------------------------
    # Assistant wiring
    # ------------------------------------------------------------------

    def get_assistant_workspace(self) -> Any:
        """Return the workspace row binding this job's assistant sessions.

        The owning project's workspace, else the global cronjobs row.
        Shared by ``get_assistant_session`` and UI panels so both bind
        the same row.
        """
        from runtime.workspace.workspaces import Workspaces

        project = self.project
        if project is not None:
            return Workspaces.for_project(project)
        return Workspaces.ensure_named(
            "System cronjobs",
            self.get_source_dir(),
            "User-scope cronjob manifests",
        )

    def get_assistant_session(self, caller: Any = None, name: str | None = None) -> Any | None:
        """Return the singleton ``cronjob_assistant`` session in this scope."""
        from runtime.session.sessions import Sessions

        return Sessions().assistant_session(
            name or self.ASSISTANT,
            project=self.project,
            workspace=self.get_assistant_workspace(),
            caller=caller,
        )
