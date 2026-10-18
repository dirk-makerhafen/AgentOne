from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from croniter import croniter
from django.db.models import QuerySet
from django.utils import timezone

from runtime.assistant_scope import AssistantScopeMixin
from server.models.content import GenericContent
from server.models.cron import Cronjob


class Cronjobs(AssistantScopeMixin):
    """Query interface for Cronjob instances.

    Scoping is explicit and strict: ``parent_project`` selects that
    project's jobs; ``parent_workspace`` selects jobs bound to that
    workspace; both *None* selects global jobs only. (Deliberately no
    global union and no agent scoping.)
    """

    #: Collection domain label (used for the global system workspace name).
    DOMAIN = "cronjobs"
    #: Internal assistant pair managing cronjobs (singular, plural).
    ASSISTANT_NAMES = ("cronjob_assistant", "cronjobs_assistant")

    def __init__(
        self,
        parent_project: Any = None,
        parent_workspace: Any = None,
    ) -> None:
        self.parent_project = parent_project
        self.parent_workspace = parent_workspace

    def _base(self) -> QuerySet[Cronjob]:
        """Unscoped base when bare (scheduler-safe), scoped otherwise."""
        if self.parent_workspace is not None:
            return Cronjob.objects.filter(workspace=self.parent_workspace)
        if self.parent_project is not None:
            return Cronjob.objects.filter(parent_project=self.parent_project)
        return Cronjob.objects.all()

    def all(self) -> QuerySet[Cronjob]:
        """Return cron jobs in scope, ordered by name.

        Bare (no parent) means global jobs only — the assistant scope.
        Schedulers needing every job use :meth:`due` (unscoped when bare).
        """
        if self.parent_workspace is not None:
            qs = Cronjob.objects.filter(workspace=self.parent_workspace)
        elif self.parent_project is not None:
            qs = Cronjob.objects.filter(parent_project=self.parent_project)
        else:
            qs = Cronjob.objects.filter(parent_project__isnull=True)
        return qs.select_related("agent", "workspace", "message").order_by("name")

    def root(self) -> QuerySet[Cronjob]:
        """Return all cron jobs (unscoped; UI + legacy callers)."""
        return Cronjob.objects.all()

    def list_cronjobs(self) -> list:
        """Return cron jobs in scope as wrapped :class:`Cron` objects."""
        from runtime.cron.cron import Cron

        return [Cron(model) for model in self.all()]

    def active(self) -> QuerySet[Cronjob]:
        """Return only active cron jobs (scoped when a parent is set)."""
        return self._base().filter(is_active=True)

    def due(self) -> QuerySet[Cronjob]:
        """Return active cron jobs that are due to run now.

        Unscoped when bare (the scheduler sees every job); scoped to the
        parent otherwise.
        """
        now = timezone.now()
        return self._base().filter(
            is_active=True,
            next_run_at__lte=now,
        )

    def _compute_next_run(self, schedule: str) -> Any:
        """Compute next run datetime from a cron expression, or None."""
        try:
            return croniter(schedule, timezone.localtime()).get_next(datetime)
        except (ValueError, KeyError):
            return None

    def create(
        self,
        name: str,
        schedule: str,
        agent_id: int,
        description: str = "",
        is_active: bool = True,
        session_mode: str = "new",
        session_name: str = "",
        message_content: str = "",
        function_type: str = "",
        function_name: str = "",
        workspace_id: int | None = None,
    ) -> Cronjob:
        """Create a new cron job with a GenericContent for the message."""
        message = None
        if message_content:
            message = GenericContent.from_text(message_content)
        return Cronjob.objects.create(
            name=name,
            description=description,
            schedule=schedule,
            is_active=is_active,
            agent_id=agent_id,
            session_mode=session_mode,
            session_name=session_name,
            message=message,
            function_type=function_type,
            function_name=function_name,
            workspace_id=workspace_id,
            next_run_at=self._compute_next_run(schedule),
        )

    def update(self, cronjob: Cronjob, **kwargs: Any) -> Cronjob:
        """Update fields on a cron job."""
        for key, value in kwargs.items():
            setattr(cronjob, key, value)
        cronjob.save()
        return cronjob

    def delete(self, cronjob: Cronjob) -> None:
        """Delete a cron job."""
        cronjob.delete()

    # ------------------------------------------------------------------
    # Assistant wiring
    # ------------------------------------------------------------------

    def get_source_dir(self) -> Path:
        """Return the source directory anchoring this scope (no I/O).

        Canonical cron file location via ``runtime.cron.file_io`` (project
        manifest ``cronjobs/`` or the global tree); a parent workspace
        resolves to its own manifest (or path).
        """
        if self.parent_workspace is not None:
            from runtime.paths import model_manifest_dir

            return model_manifest_dir(self.parent_workspace, "workspace")
        from runtime.cron.file_io import cron_file_path

        return cron_file_path(".scope", self.parent_project).parent

    def get_assistant_workspace(self) -> Any:
        """Return the workspace row binding this scope's assistant sessions.

        Project scope: project workspace; global: system row. Shared by
        ``get_assistant_session`` and UI panels so both bind the same row.
        """
        from runtime.workspace.workspaces import Workspaces

        project = self.project
        if project is not None:
            return Workspaces.for_project(project)
        return Workspaces.ensure_named(
            "System cronjobs", self.get_source_dir(), "User-scope cronjob manifests"
        )
