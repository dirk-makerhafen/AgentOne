"""WorkItem — a durable unit of *work*, above the execution layer.

``AgentTaskCall`` records one invocation of one tool; this records *a thing
someone wants done*, which may take days and many agent turns.  See
``docs/work-items.md`` for the design.

Invariants this model must preserve:

* ``status`` is written **only** by :mod:`runtime.workitems.workitem_fsm`.
  No ATC/Run FSM code may touch it — the arrow between the two lifecycles
  points one way (``docs/work-items.md`` §2.2).
* A work item may sit in ``ready`` indefinitely, so nothing in the dispatch
  path may apply the 24h ``_is_ancient`` turn-death guard (§2.3).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import models

from server.models.base_model import BaseModel, Observables
from server.models.workitems.enums import WorkItemStatus, WorkItemVerifyStatus

#: Reject → re-queue → verify cycles allowed before escalating to a human.
#: Bounded because the cycle spans separate dispatches, days apart
#: (``docs/work-items.md`` §8.5).  Overridable per project later; a module
#: constant keeps increment 1 free of new settings surface.
MAX_VERIFY_ATTEMPTS = 3


class WorkItem(BaseModel):
    """A durable, verifiable unit of work."""

    class WorkItemObservables(Observables):
        """Explicit observable keys for a WorkItem (IDE autocomplete)."""

        @property
        def child_items(self):
            return f"WorkItem.parent:{self.model.pk}"

    #: Human-facing reason the item is blocked / rejected, plus a result summary.
    last_outcome: str = models.TextField(default="", blank=True)

    # ------------------------------------------------------------------
    # Decomposition
    # ------------------------------------------------------------------
    project = models.ForeignKey(
        "server.Project",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="work_items",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="child_items",
    )

    # ------------------------------------------------------------------
    # The requirement
    # ------------------------------------------------------------------
    title: str = models.CharField(max_length=255, default="", blank=True)
    body: str = models.TextField(default="", blank=True)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    status: str = models.CharField(
        max_length=20,
        choices=WorkItemStatus.choices,
        default=WorkItemStatus.BACKLOG,
        db_index=True,
    )
    priority: int = models.IntegerField(default=0)
    order: int = models.IntegerField(default=0)
    started_at: datetime | None = models.DateTimeField(null=True, blank=True, default=None)
    completed_at: datetime | None = models.DateTimeField(null=True, blank=True, default=None)

    # ------------------------------------------------------------------
    # Assignment and execution
    # ------------------------------------------------------------------
    assigned_agent = models.ForeignKey(
        "server.AgentModel",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="work_items",
    )
    executor_session = models.ForeignKey(
        "server.SessionModel",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="related_work_items",
    )
    root_task = models.ForeignKey(
        "server.AgentTaskCall",
        on_delete=models.SET_NULL,
        default=None,
        null=True,
        blank=True,
        related_name="related_work_items",
    )
    dispatch_count: int = models.IntegerField(default=0)

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    requires_verification: bool = models.BooleanField(default=False)
    verify_status: str = models.CharField(
        max_length=20,
        choices=WorkItemVerifyStatus.choices,
        default=None,
        null=True,
        blank=True,
    )
    verify_reason: str = models.TextField(default="", blank=True)
    verify_attempts: int = models.IntegerField(default=0)

    class Meta:
        ordering = ["-priority", "created_at"]

    def __str__(self) -> str:
        return f"WorkItem #{self.pk} [{self.status}] {self.title[:60]}"

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def verify_attempts_exhausted(self) -> bool:
        """True when the reject→re-verify cycle has hit its bound."""
        return self.verify_attempts >= MAX_VERIFY_ATTEMPTS

    def summarise(self) -> dict[str, Any]:
        """Compact dict for tool results and the verification brief."""
        return {
            "id": self.pk,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "project": self.project_id,
            "parent": self.parent_id,
            "assigned_agent": self.assigned_agent.name if self.assigned_agent_id else None,
            "requires_verification": self.requires_verification,
            "verify_status": self.verify_status,
            "verify_attempts": self.verify_attempts,
            "dispatch_count": self.dispatch_count,
            "last_outcome": self.last_outcome,
        }

    def summarise_with_body(self) -> dict[str, Any]:
        """Like :meth:`summarise` plus the requirement text.

        ``summarise`` omits ``body`` on purpose — it is the compact form used
        where the requirement was just supplied. But ``workitem_create`` and
        ``workitem_update`` return it for an item the agent may not be looking
        at any more, and without the body the agent cannot recover what it
        actually asked for. Since the author already has the text in context,
        echoing it back is the cheaper fix than a separate get tool.
        """
        summary = self.summarise()
        summary["body"] = self.body or ""
        return summary
