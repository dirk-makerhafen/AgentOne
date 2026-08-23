"""Workspace model representing a working directory on a system."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import models
from server.models.base_model import BaseModel, Observables


class WorkspaceModel(models.Model):
    """A named workspace bound to a filesystem path."""

    class WorkspaceModelObservables(Observables):
        @property
        def cron_jobs(self):
            return f"Cronjob.workspace:{self.model.pk}"

    created_at: datetime = models.DateTimeField(auto_now_add=True)
    updated_at: datetime = models.DateTimeField(auto_now=True)

    name: str = models.CharField(default="", max_length=4096, help_text="")
    description: str = models.TextField(default="", max_length=10000, help_text="")
    path: str = models.CharField(max_length=4096, help_text="")

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
