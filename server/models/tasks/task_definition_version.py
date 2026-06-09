from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from sortedm2m.fields import SortedManyToManyField

from server.models.base_model import BaseModel
from server.models.enums.task_enums import TaskExecutionMode, TaskType


class TaskDefinitionVersion(BaseModel):
    """A versioned snapshot of a task definition's configuration."""

    task_definition = models.ForeignKey(
        "server.TaskDefinition",
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="versions",
    )

    description = models.TextField()
    function_schema = models.JSONField()

    task_type = models.CharField(max_length=20, choices=TaskType.choices)
    task_execution_mode = models.CharField(
        max_length=20, choices=TaskExecutionMode.choices, default=TaskExecutionMode.FUNCTION
    )

    requires_approval = models.BooleanField(default=False)
    bound = models.BooleanField(default=False)

    time_limit = models.IntegerField(default=None, null=True)
    max_subtask_errors = models.IntegerField(default=0)
    max_subtask_error_rate = models.IntegerField(default=0)
    limit_subtask_parallel_runs = models.IntegerField(default=0)
    limit_per_instance_parallel_runs = models.IntegerField(default=1)
    priority = models.IntegerField(default=0)

    max_retries = models.IntegerField(default=0)
    retry_delay = models.IntegerField(default=10)
    retry_requires_approval = models.BooleanField(default=True)

    function_name = models.CharField(max_length=255, default="", blank=True)

    path = models.CharField(max_length=1024, default=None, blank=True, null=True)
    commit = models.CharField(max_length=1024, default="")

    child_tasks = SortedManyToManyField(
        "self", help_text="", symmetrical=False, blank=True, related_name="parent_tasks"
    )

    @property
    def task_instances(self):
        """Return related TaskInstance queryset."""
        return self.related_task_instances  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def agent_versions(self):
        """Return related AgentVersionModel queryset."""
        return self.related_agent_versions  # pyright: ignore[reportAttributeAccessIssue]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Prevent updates to existing TaskDefinitionVersion instances."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        name = self.task_definition.name if self.task_definition else ""
        return f"TaskDefinitionVersion[{name} pk:{self.pk}]"
