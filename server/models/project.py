"""Project model representing a code / workspace project."""
from __future__ import annotations
from datetime import datetime
from django.db import models
from server.models.base_model import ObservableMixin, Observables


class Project(ObservableMixin, models.Model):
    """A named project with an optional primary workspace folder."""

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
        @property
        def cron_jobs(self):
            return f"Cronjob.parent_project:{self.model.pk}"
        @property
        def task_definitions(self):
            return f"TaskDefinition.parent_project:{self.model.pk}"
        @property
        def work_items(self):
            return f"WorkItem.project:{self.model.pk}"

    created_at: datetime = models.DateTimeField(auto_now_add=True)
    updated_at: datetime = models.DateTimeField(auto_now=True)

    name: str = models.CharField(default="", max_length=255, help_text="")
    description: str = models.TextField(default="", max_length=10000, help_text="")

    # Folder handling (DB-canonical; project.md / projects.yaml deprecated).
    # The project's filesystem folder is its primary workspace
    # (``main_workspace``); the old ``path`` column was folded into it.
    # manifest_dir: the .agentone manifest tree for this project. Blank =
    # central default ~/.agentone/projects/<name> (see
    # runtime.paths.project_manifest_dir). Never git-tracked.
    manifest_dir: str = models.CharField(max_length=1024, default="", blank=True)
    # storage: inline_project | inline_workspace | central | git
    storage: str = models.CharField(max_length=32, default="", blank=True)
    git_url: str = models.CharField(max_length=1024, default="", blank=True)
    git_ref: str = models.CharField(max_length=255, default="", blank=True)
    main_workspace = models.ForeignKey(
        "server.WorkspaceModel", default=None, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="primary_for_projects",
    )

    @property
    def path(self) -> str:
        """Return the primary workspace folder (read-only ``path`` alias).

        The DB ``path`` column is gone — a project's folder is its
        ``main_workspace``. Kept as a convenience for templates and runtime
        callers that still read ``project.path``.
        """
        ws = getattr(self, "main_workspace", None)
        return getattr(ws, "path", "") or ""


    def refresh_from_disk(self, details=None) -> None:
        """Reload this project's manifest tree (agents/skills/scripts/crons) from disk."""
        from runtime.paths import project_manifest_dir
        from registry.loader.load_project_folder import load_scope_dir

        manifest = project_manifest_dir(self)
        if details is None:
            details = []
        load_scope_dir(manifest, self, details=details)
        self.refresh_from_db()
