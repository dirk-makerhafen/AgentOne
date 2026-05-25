"""Cronjob model for scheduling periodic agent runs."""
from __future__ import annotations

from datetime import datetime

from django.db import models

from server.models.content import GenericContent


class Cronjob(models.Model):
    """A scheduled job that runs an agent on a recurring schedule."""

    SESSION_MODE_CHOICES = [ ("new", "New session each run"), ("existing", "Reuse existing session"),
    ]

    FUNCTION_TYPE_CHOICES = [ 
        ("", "Send message (ingest_user_message)"), 
        ("task", "Task"), 
        ("tool", "Tool"), 
        ("command", "Command"),
    ]

    created_at: datetime = models.DateTimeField(auto_now_add=True)
    updated_at: datetime = models.DateTimeField(auto_now=True)

    name: str = models.CharField(default="", max_length=255, help_text="")
    description: str = models.TextField( default="", max_length=10000, help_text="")
    schedule: str = models.CharField(max_length=2048, help_text="")
    is_active: bool = models.BooleanField(default=True)
    agent: models.ForeignKey | None = models.ForeignKey( "server.AgentModel", on_delete=models.CASCADE, related_name="related_cron", blank=True, null=True)

    # Session
    session_mode: str = models.CharField(max_length=20, choices=SESSION_MODE_CHOICES, default="new")
    session_name: str = models.CharField(max_length=255, blank=True, default="", help_text="Session name for existing-session mode. Leave blank for auto-name.")

    # Message (replaces prompt)
    message: GenericContent | None = models.ForeignKey( GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="related_cron_message")

    # Function target
    function_type: str = models.CharField(max_length=20, choices=FUNCTION_TYPE_CHOICES, blank=True, default="")
    function_name: str = models.CharField(max_length=255, blank=True, default="", help_text="Name of the task/tool/command to execute.")

    # Named pipe output
    pipe_names: list = models.JSONField(default=list, blank=True, help_text="Published to these named pipes after each run.")

    # Tracking
    last_run_at: datetime | None = models.DateTimeField(null=True, blank=True, default=None)
    next_run_at: datetime | None = models.DateTimeField(null=True, blank=True, default=None)
    last_status: str = models.CharField(max_length=50, blank=True, default="")
    total_runs: int = models.IntegerField(default=0)
