from __future__ import annotations

from typing import Any

from django.db import models

from server.models.base_model import ObservableMixin


class SkillModelVersion(ObservableMixin, models.Model):
    """A specific versioned snapshot of a skill's configuration."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    skill = models.ForeignKey("server.SkillModel",default=None,null=True,on_delete=models.CASCADE,related_name="versions")

    description = models.TextField(max_length=1024, default="")
    commit = models.TextField(max_length=1024, default="")

    path = models.CharField(default="", max_length=255, help_text="")
    version_number = models.IntegerField(default=0)

