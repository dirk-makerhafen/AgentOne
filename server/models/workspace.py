"""Workspace model representing a working directory on a system."""
from __future__ import annotations

import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from server.models.base_model import BaseModel, ObservableMixin, Observables


WORKSPACE_COLOR_PALETTE = [
    "#ef4444",
    "#f97316",
    "#f59e0b",
    "#84cc16",
    "#22c55e",
    "#14b8a6",
    "#06b6d4",
    "#3b82f6",
    "#6366f1",
    "#8b5cf6",
    "#d946ef",
    "#ec4899",
]

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def random_workspace_color() -> str:
    """Pick a random color from the workspace palette."""
    return random.choice(WORKSPACE_COLOR_PALETTE)


def validate_workspace_color(value: str) -> None:
    """Ensure the color is a #rrggbb hex string."""
    if not value or not _COLOR_RE.match(value):
        raise ValidationError("Color must be a #rrggbb hex string.")


class WorkspaceModel(ObservableMixin, models.Model):
    """A named workspace bound to a filesystem path."""

    class WorkspaceModelObservables(Observables):
        @property
        def cron_jobs(self):
            return f"Cronjob.workspace:{self.model.pk}"
        @property
        def session_versions(self):
            return f"SessionVersionModel.workspace:{self.model.pk}"
        @property
        def terminals(self):
            return f"TerminalSession.workspace:{self.model.pk}"

    created_at: datetime = models.DateTimeField(auto_now_add=True)
    updated_at: datetime = models.DateTimeField(auto_now=True)

    name: str = models.CharField(default="", max_length=4096, help_text="")
    description: str = models.TextField(default="", max_length=10000, help_text="")
    path: str = models.CharField(max_length=4096, help_text="")
    color: str = models.CharField(
        default=random_workspace_color,
        max_length=7,
        help_text="Workspace accent color as a #rrggbb hex string.",
        validators=[validate_workspace_color],
    )

    access: Any = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Filesystem access policy for paths inside this workspace. "
            "Shape: {\"read\": {\"default\": \"allow|ask|deny\", \"allow\": [], "
            "\"ask\": [], \"deny\": []}, \"write\": {...}}. Patterns are "
            "workspace-relative globs."
        ),
    )

    # Folder handling (DB-canonical; workspace.md never existed as a file).
    parent_project = models.ForeignKey(
        "server.Project", default=None, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="workspaces",
    )
    # agentone_dir: workspace-scoped .agentone tree; may be any directory the
    # user chose. Never blank — when not set explicitly it defaults to the
    # owning project's tree, else the user home (see save()). The chosen
    # location *type* is not stored; only the resulting directory.
    agentone_dir: str = models.CharField(max_length=4096, default="", blank=False)

    def save(self, *args, **kwargs) -> None:
        if not (self.agentone_dir or "").strip():
            self.agentone_dir = self.get_agentone_dir().as_posix()
        super().save(*args, **kwargs)

    def get_agentone_dir(self) -> Path:
        """Return this workspace's manifest directory (no writes).

        Prefers the stored ``agentone_dir``; otherwise derives the default
        location: ``<project agentone dir>/workspaces/<name>`` when the
        workspace is project-owned, else ``~/.agentone/workspaces/<name>``.
        """
        from runtime.paths import central_workspace_dir

        stored = str(self.agentone_dir or "").strip()
        if stored:
            return Path(stored).expanduser()
        name = (self.name or "").strip()
        safe = name.replace(" ", "_").replace("/", "_") or (
            Path(self.path).name if (self.path or "").strip() else "unnamed"
        )
        return central_workspace_dir(safe, project=self.parent_project)

    @property
    def dashboard_index(self) -> Path:
        """Return the dashboard ``index.md`` path for this workspace."""
        return self.get_agentone_dir() / "dashboard" / "index.md"

    def refresh_from_disk(self, details=None) -> None:
        """Reload this workspace's scoped manifest tree from disk."""
        from registry.loader.load_project_folder import load_workspace_scope

        manifest = self.get_agentone_dir()
        if not manifest.is_dir():
            return
        project = self.parent_project
        if project is None:
            return
        if details is None:
            details = []
        load_workspace_scope(manifest, project, details=details)
        self.refresh_from_db()
