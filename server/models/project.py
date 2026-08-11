"""Project model representing a code / workspace project."""
from __future__ import annotations

from datetime import datetime

from django.db import models

from server.models.base_model import ObservableMixin, Observables


class Project(ObservableMixin, models.Model):
    """A named project with an optional filesystem path."""

    created_at: datetime = models.DateTimeField(auto_now_add=True)
    updated_at: datetime = models.DateTimeField(auto_now=True)

    name: str = models.CharField(default="", max_length=255, help_text="")
    description: str = models.TextField(default="", max_length=10000, help_text="")
    path: str = models.CharField(max_length=255, help_text="")


    class ProjectObservables(Observables):
        """Explicit observable keys for an Project (IDE autocomplete)."""

        @property
        def child_agents(self):
            return f"AgentModel.parent_project:{self.model.pk}"

        @property
        def child_skills(self):
            return f"SkillModel.parent_project:{self.model.pk}"

        @property
        def child_sessions(self):
            return f"SessionModel.parent_project:{self.model.pk}"
