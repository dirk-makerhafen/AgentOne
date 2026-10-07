"""Database-backed session-private dynamic workflows.

Each workflow version is an immutable row pointing at content-addressed
:class:`GenericContent` (no session FK — identical definitions dedupe
across sessions); a session's *current* workflow is a link row
(:class:`SessionWorkflow`, unique per session + name).

- Save → validate the definition, then mint a new version row and move
  only the writer's link.  Siblings and forks keep pointing at their own
  versions.  Saving identical content+metadata is a no-op (no new
  version).
- Fork → copy the parent's link rows (see ``inherit_workflows`` in
  ``runtime/session_workflows.py``, called from
  ``AgentVersionModel.get_or_create_session``).
- Delete → remove the link row only.  Version rows stay as the audit
  trail (author, timestamp, source); they are never garbage-collected
  in v1 — same convention as ad-hoc tools
  (``server/models/adhoc_tool.py``) and query templates
  (``server/models/queries/query_template.py``).

Runs pin a version pk (``workflow_run``), never the link, so editing or
deleting a workflow mid-run cannot change the running execution.  Run
state itself lives in the ``AgentTaskCall``/``AgentTaskRun`` graph, not
in these tables — there is no ``WorkflowRun`` table in v1.

Definitions are validated once at write time (same DSL checks as
``workflow_validate``); reads never re-validate because version rows
are immutable.
"""
from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from server.models.base_model import BaseModel, Observables


class WorkflowVersion(BaseModel):
    """One immutable snapshot of a workflow definition (canonical JSON)."""

    class WorkflowVersionObservables(Observables):
        """Explicit observable keys for a WorkflowVersion (IDE autocomplete)."""
        pass

    content = models.ForeignKey(
        "server.GenericContent",
        on_delete=models.PROTECT,
        related_name="workflow_versions",
        help_text="Canonical workflow JSON (name, description, inputs_schema, "
        "steps), content-addressed.",
    )
    name = models.CharField(
        max_length=255,
        help_text="Denormalized workflow name so lineage queries never have "
        "to join content blobs.",
    )
    description = models.TextField(
        default="",
        blank=True,
        help_text="One-line description shown by workflow_list.",
    )
    created_by_session = models.ForeignKey(
        "server.SessionModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
        related_name="created_workflow_versions",
        help_text="Session that minted this version (audit); NULL when unknown. "
        "SET_NULL so session deletion never erases authorship.",
    )
    source = models.CharField(
        max_length=30,
        default="",
        blank=True,
        help_text="How the version was created: tool, migrate, ...",
    )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Prevent updates to existing version rows (append-only history)."""
        if self.pk:
            raise ValidationError(f"You may not edit an existing {self._meta.model_name}")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"<WorkflowVersion[{self.pk}] {self.name}>"


class SessionWorkflow(BaseModel):
    """A session's current pointer to one workflow version (the link row)."""

    class SessionWorkflowObservables(Observables):
        """Explicit observable keys for a SessionWorkflow (IDE autocomplete)."""
        @property
        def session_workflows(self):  # type: ignore[no-untyped-def]
            return f"SessionWorkflow.session:{self.model.pk}"

    session = models.ForeignKey(
        "server.SessionModel",
        on_delete=models.CASCADE,
        related_name="workflow_links",
    )
    name = models.CharField(
        max_length=255,
        help_text="Workflow name (lowercase letter first, then lowercase/digits/_).",
    )
    version = models.ForeignKey(
        "server.WorkflowVersion",
        on_delete=models.PROTECT,
        related_name="session_links",
        help_text="Current version. PROTECT: a linked version must never vanish.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "name"],
                name="uniq_session_workflow_name",
            ),
        ]

    def __str__(self) -> str:
        return f"<SessionWorkflow[{self.pk}] session={self.session_id} name={self.name}>"
