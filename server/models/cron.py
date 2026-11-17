"""Cronjob model for scheduling periodic agent runs."""
from __future__ import annotations

from datetime import datetime

from django.db import models

from server.models.base_model import BaseModel
from server.models.content import GenericContent


class Cronjob(BaseModel):
    """A scheduled job that runs an agent on a recurring schedule."""
    
    SESSION_MODE_CHOICES = [ ("new", "New session each run"), ("existing", "Reuse existing session"),]

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
    is_archived: bool = models.BooleanField(default=False)
    agent: models.ForeignKey | None = models.ForeignKey( "server.AgentModel", on_delete=models.CASCADE, related_name="related_cron", blank=True, null=True)
    parent_project = models.ForeignKey("server.Project",default=None,null=True,blank=True,on_delete=models.CASCADE,related_name="child_crons")
    workspace = models.ForeignKey("server.WorkspaceModel",default=None,null=True,blank=True,on_delete=models.SET_NULL,related_name="cron_jobs")
    # Legacy field from the removed cron manifest files; kept for schema
    # compatibility. Cron jobs are now DB-canonical and created via the UI.
    manifest_dir: str = models.CharField(max_length=1024, default="", blank=True)

    # Session
    session_mode: str = models.CharField(max_length=20, choices=SESSION_MODE_CHOICES, default="new")
    session_name: str = models.CharField(max_length=255, blank=True, default="", help_text="Session name for existing-session mode. Leave blank for auto-name.")

    # Message (replaces prompt)
    message: GenericContent | None = models.ForeignKey( GenericContent, default=None, null=True, blank=True, on_delete=models.SET_DEFAULT, related_name="related_cron_message")

    # Function target
    function_type: str = models.CharField(max_length=20, choices=FUNCTION_TYPE_CHOICES, blank=True, default="")
    function_name: str = models.CharField(max_length=255, blank=True, default="", help_text="Name of the task/tool/command to execute.")

    # Tracking
    last_run_at: datetime | None = models.DateTimeField(null=True, blank=True, default=None)
    next_run_at: datetime | None = models.DateTimeField(null=True, blank=True, default=None)
    last_status: str = models.CharField(max_length=50, blank=True, default="")
    total_runs: int = models.IntegerField(default=0)

    def _schedule_changed(self, update_fields) -> bool:
        """Return whether ``schedule`` differs from the stored row."""
        if self._state.adding or self.pk is None:
            return False
        if update_fields is not None and "schedule" not in update_fields:
            return False
        previous = (
            type(self).objects.filter(pk=self.pk)
            .values_list("schedule", flat=True)
            .first()
        )
        return previous is not None and previous != self.schedule

    def save(self, *args, **kwargs) -> None:
        """Save the row, keeping ``next_run_at`` in sync with the schedule.

        This is the single choke point for admin, API, assistant and manifest
        writes: a newly created or re-scheduled active job always gets a
        ``next_run_at``, and disabling a job clears it so it cannot be due.
        """
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and not isinstance(update_fields, list):
            update_fields = list(update_fields)
            kwargs["update_fields"] = update_fields

        changed_fields: list[str] = []
        if not self.is_active:
            if self.next_run_at is not None:
                self.next_run_at = None
                changed_fields.append("next_run_at")
        elif self.next_run_at is None or self._schedule_changed(update_fields):
            from runtime.cron.schedule import compute_next_run

            next_run_at = compute_next_run(self.schedule)
            if next_run_at != self.next_run_at:
                self.next_run_at = next_run_at
                changed_fields.append("next_run_at")

        if update_fields is not None:
            for field_name in changed_fields:
                if field_name not in update_fields:
                    update_fields.append(field_name)

        super().save(*args, **kwargs)

    def refresh_from_disk(self, details=None) -> None:
        """Cron jobs are DB-canonical; no manifest files to reload."""
        if details is not None:
            details.append(
                {
                    "name": self.name,
                    "type": "cron",
                    "action": "skipped",
                    "message": "Cron jobs are DB-canonical and no longer use .md manifest files.",
                }
            )
        self.refresh_from_db()
