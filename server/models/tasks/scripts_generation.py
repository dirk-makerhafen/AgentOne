from django.core.exceptions import ValidationError
from django.db import models

from server.models.base_model import BaseModel, Observables


class ScriptsGeneration(BaseModel):
    """A generation (snapshot) of all global script task definitions.

    Each reload of the global scripts directory produces one generation,
    identified by the git tree SHA commit.  Only TaskDefinitions belonging
    to the latest generation are considered "current" and available for
    agent resolution.
    """

    class ScriptsGenerationObservables(Observables):
        """Explicit observable keys for a ScriptsGeneration (IDE autocomplete)."""
        @property
        def task_definitions(self):
            return f"TaskDefinition.parent_generation:{self.model.pk}"

    commit = models.CharField(max_length=1024, default="")

    class Meta:
        verbose_name = "Scripts Generation"
        verbose_name_plural = "Scripts Generations"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ScriptsGeneration[commit={self.commit[:12]} pk:{self.pk}]"

    def save(self, *args, **kwargs) -> None:
        """Prevent updates to existing ScriptsGeneration instances."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)
