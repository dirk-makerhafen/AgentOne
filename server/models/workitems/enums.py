"""Enumerations for the long-term work-item layer."""
from __future__ import annotations

from django.db import models


class WorkItemStatus(models.TextChoices):
    """Lifecycle state of a durable work item.

    The work layer has its own time scale (days to weeks) and must never
    share a state machine with :class:`TaskCallStatusDetail` (ms to minutes).
    See ``docs/work-items.md`` §2.2 — no ATC/Run FSM code may write these.
    """

    BACKLOG = "backlog", "Backlog"
    READY = "ready", "Ready"
    IN_PROGRESS = "in_progress", "In Progress"
    IN_REVIEW = "in_review", "In Review"
    BLOCKED = "blocked", "Blocked"
    DONE = "done", "Done"
    CANCELLED = "cancelled", "Cancelled"


class WorkItemVerifyStatus(models.TextChoices):
    """Agent-review outcome for a work item flagged ``requires_verification``.

    Mirrors the ``auto_review_status`` vocabulary of
    :class:`~server.models.enums.task_enums.TaskCallStatusDetail` consumers so
    the two review systems read alike, but is a separate concern: this one
    judges the *goal*, not a tool invocation.
    """

    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    ESCALATED = "escalated", "Escalated to human"
    SKIPPED = "skipped", "Skipped"


class WorkItemDecision(models.TextChoices):
    """Verdict an agent reviewer may render on a work item."""

    APPROVE = "approve", "Approve — the work satisfies its requirement"
    REJECT = "reject", "Reject — the work does not satisfy its requirement"
    ASK_HUMAN = "ask_human", "Escalate to a human"
