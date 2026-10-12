from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from server.models.base_model import ObservableMixin, Observables


class SkillModelVersion(ObservableMixin, models.Model):
    """A specific versioned snapshot of a skill's configuration."""

    class SkillModelVersionObservables(Observables):
        """Explicit observable keys for a SkillModelVersion (IDE autocomplete)."""
        @property
        def newest_for_skills(self):
            return f"SkillModel.latest_skill_version:{self.model.pk}"

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    skill = models.ForeignKey("server.SkillModel",default=None,null=True,on_delete=models.CASCADE,related_name="versions")

    description = models.TextField(max_length=1024, default="")
    commit = models.TextField(max_length=1024, default="")

    path = models.CharField(default="", max_length=255, help_text="")
    version_number = models.IntegerField(default=0)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Prevent updates to existing SkillModelVersion instances."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

