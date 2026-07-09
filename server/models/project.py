"""Project model representing a code / workspace project."""
from __future__ import annotations

from datetime import datetime

from django.db import models


class Project(models.Model):
    """A named project with an optional filesystem path."""

    created_at: datetime = models.DateTimeField(auto_now_add=True)
    updated_at: datetime = models.DateTimeField(auto_now=True)

    name: str = models.CharField(default="", max_length=255, help_text="")
    description: str = models.TextField(default="", max_length=10000, help_text="")
    path: str = models.CharField(max_length=255, help_text="")
