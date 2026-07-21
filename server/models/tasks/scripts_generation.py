from django.db import models

from server.models.base_model import BaseModel


class ScriptsGeneration(BaseModel):
    """A generation (snapshot) of all global script task definitions.

    Each reload of the global scripts directory produces one generation,
    identified by the git tree SHA commit.  Only TaskDefinitions belonging
    to the latest generation are considered "current" and available for
    agent resolution.
    """

    commit = models.CharField(max_length=1024, default="")

    class Meta:
        verbose_name = "Scripts Generation"
        verbose_name_plural = "Scripts Generations"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ScriptsGeneration[commit={self.commit[:12]} pk:{self.pk}]"
