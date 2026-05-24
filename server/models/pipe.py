"""NamedPipe model — named channels for decoupled task-to-task data flow.

Producers (AgentTaskCalls) publish their output to named pipes by listing
pipe names in ``pipe_output_names``. Consumers (NamedPipeSubscriptions) bind
a ``TaskDefinitionVersion`` to a pipe; the tick scheduler dispatches new items
automatically.
"""
from __future__ import annotations

from django.db import models


class NamedPipe(models.Model):
    """A named channel that task calls can publish output to."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Named Pipe"
        verbose_name_plural = "Named Pipes"

    def __str__(self) -> str:
        return self.name


class NamedPipeSubscription(models.Model):
    """Binds a consumer ``TaskDefinitionVersion`` to a ``NamedPipe``.

    When a task call completes with ``ENDED_SUCCESS`` and lists the pipe name
    in its ``pipe_output_names``, the tick scheduler checks whether the
    consumer has already processed that item (dedup via ``carguments_json``)
    and, if not, creates and enqueues a new ``AgentTaskCall``.
    """

    SESSION_MODE_CHOICES = [
        ("new", "New session each run"),
        ("existing", "Reuse existing session"),
    ]

    pipe = models.ForeignKey(
        NamedPipe,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    consumer_task = models.ForeignKey(
        "TaskDefinitionVersion",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)
    arguments_template = models.JSONField(default=dict, blank=True)

    agent = models.ForeignKey(
        "AgentModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Agent to use for consumer task calls. Leave empty to use the task definition's default agent.",
    )
    session_mode = models.CharField(
        max_length=20,
        choices=SESSION_MODE_CHOICES,
        default="new",
    )
    session_name = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Session name for existing-session mode.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("pipe", "consumer_task")
        verbose_name = "Pipe Subscription"
        verbose_name_plural = "Pipe Subscriptions"

    def __str__(self) -> str:
        return (
            f"{self.name or self.pipe.name} \u2192 {self.consumer_task}"
        )
