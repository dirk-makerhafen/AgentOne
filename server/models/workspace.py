"""Workspace model representing a working directory on a system."""
from __future__ import annotations

import random
import re
from datetime import datetime
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
    # storage: inline | central
    storage: str = models.CharField(max_length=32, default="", blank=True)
    # manifest_dir: workspace-scoped .agentone tree. Blank = unmanaged
    # (workspace is a bare cwd with no manifests of its own).
    manifest_dir: str = models.CharField(max_length=4096, default="", blank=True)

    def refresh_from_disk(self, details=None) -> None:
        """Reload this workspace's scoped manifest tree from disk."""
        from pathlib import Path

        from runtime.paths import workspace_manifest_dir
        from registry.loader.load_project_folder import load_scope_dir

        manifest = workspace_manifest_dir(self)
        if manifest is None or not manifest.is_dir():
            return
        project = self.parent_project
        if project is None:
            return
        if details is None:
            details = []
        load_scope_dir(manifest, project, details=details)
        self.refresh_from_db()
