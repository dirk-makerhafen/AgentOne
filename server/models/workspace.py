"""Workspace model representing a working directory on a system."""
from __future__ import annotations

from datetime import datetime

from django.db import models


class WorkspaceModel(models.Model):
    """A named workspace bound to a filesystem path."""

    created_at: datetime = models.DateTimeField(auto_now_add=True)
    updated_at: datetime = models.DateTimeField(auto_now=True)

    name: str = models.CharField(default="", max_length=4096, help_text="")
    description: str = models.TextField(default="", max_length=10000, help_text="")
    path: str = models.CharField(max_length=4096, help_text="")

    observable_fields = set([
        "pk",
    ])

    @property
    def observable_keys(self):
        return set([
            "WorkspaceModel",
            f"WorkspaceModel.pk:{self.pk}",
        ])