"""Cronjob model for scheduling periodic agent runs."""
from __future__ import annotations

from datetime import datetime

from django.db import models

from server.models.base_model import BaseModel, Observables
from server.models.content import GenericContent


class Cronjob(BaseModel):
    """A scheduled job that runs an agent on a recurring schedule."""
    class CronjobObservables(Observables):
        """Explicit observable keys for an Cronjob (IDE autocomplete)."""
        @property
        def calls(self):
            return f"AgentTaskCall.cronjob:{self.model.pk}"
    
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
    # manifest_dir: directory holding this cron's .md manifest (set by the
    # loader; blank for rows predating the field or created ad hoc / in-DB).
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

    def refresh_from_disk(self, details=None) -> None:
        """Reload this cron job from disk.

        Prefers the canonical project/global ``cronjobs/`` directory, then
        the directory the job was loaded from (``manifest_dir``).  The
        canonical file is authoritative, so a stale workspace copy cannot
        shadow it; workspace-only jobs fall back to their own manifest dir.
        """
        from pathlib import Path

        from registry.loader.load_cron_manifest import load_cron_manifest
        from runtime.cron.file_io import _find_cron_file, cron_file_path
        from runtime.refresh import install_repo_for_path

        candidates: list[Path] = [cron_file_path(self.name, self.parent_project).parent]
        stored = (self.manifest_dir or "").strip()
        if stored:
            candidates.append(Path(stored))

        md = None
        cron_dir = None
        for directory in candidates:
            if not directory.is_dir():
                continue
            found = _find_cron_file(directory, self.name)
            if found is not None:
                md = found
                cron_dir = directory
                break
        if md is None or cron_dir is None:
            return
        if details is None:
            details = []
        _source_root, install_repo = install_repo_for_path(cron_dir)
        try:
            install_repo.sync()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        load_cron_manifest(
            md,
            install_repo=install_repo,
            parent_project=self.parent_project,
            details=details,
        )
        self.refresh_from_db()
