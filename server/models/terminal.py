"""Persistent terminal sessions (one tmux session per named terminal).

One row per named terminal: unique within its owning AgentOne session.
The actual PTY lives in tmux (see ``runtime/terminal/manager.py``);
this model is the bookkeeping layer so terminals survive worker
restarts, show up in admin/API, and can be reaped on idle/archival.
"""
from __future__ import annotations

from typing import Any

from django.db import models

from server.models.base_model import BaseModel, Observables


class TerminalStatus(models.TextChoices):
    CREATED = "created", "Created"
    RUNNING = "running", "Running"
    DEAD = "dead", "Dead"


class TerminalSession(BaseModel):
    """A named persistent shell belonging to an AgentOne session."""

    class TerminalSessionObservables(Observables):
        """Explicit observable keys for a TerminalSession."""

    session = models.ForeignKey(
        "server.SessionModel",
        on_delete=models.CASCADE,
        related_name="terminals",
        null=True,
        blank=True,
        default=None,
    )
    workspace = models.ForeignKey(
        "server.WorkspaceModel",
        on_delete=models.SET_NULL,
        related_name="terminals",
        null=True,
        blank=True,
        default=None,
    )
    name: str = models.CharField(max_length=64, default="default")
    tmux_session_name: str = models.CharField(max_length=128, unique=True)
    status: str = models.CharField(
        max_length=16, choices=TerminalStatus.choices, default=TerminalStatus.CREATED
    )
    shell: str = models.CharField(max_length=255, default="", blank=True)
    cwd: str = models.CharField(max_length=4096, default="", blank=True)
    log_path: str = models.CharField(max_length=4096, default="", blank=True)
    last_active_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "name"],
                name="uniq_terminal_name_per_session",
            ),
        ]

    def __str__(self) -> str:
        return f"TerminalSession[{self.name} tmux:{self.tmux_session_name} pk:{self.pk}]"
