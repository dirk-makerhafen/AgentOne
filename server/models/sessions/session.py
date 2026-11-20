from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models
from django.db.models import QuerySet

from server.models.base_model import BaseModel
from server.models.enums.session_enums import SessionType
from server.models.message import Message
from server.models.queries.query import Query

if TYPE_CHECKING:
    from runtime.session.session import Session


class SessionModel(BaseModel):
    """A conversation session that versions its state over time."""


    name = models.CharField(max_length=255)
    #: False once the user has explicitly named/renamed the session.  Auto-title
    #: generation only touches sessions whose name is still system-generated.
    name_is_auto = models.BooleanField(default=True, db_index=True)
    #: Non-unique grouping key for sessions that do the same kind of work.
    #: Unlike ``name`` it is not part of any uniqueness constraint, so many
    #: baseagent/wiki/etc. sessions can share e.g. ``wiki:timeline-daily``.
    #: Convention: lowercase ``domain:task``.
    group_key = models.CharField(max_length=255, default="", blank=True, db_index=True)
    turn_count = models.IntegerField(default=0)
    unattended_turn_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    is_paused = models.BooleanField(default=False, db_index=True)
    #: Set while a ``compact_turn`` chain owns this session.  While true,
    #: ordinary chat messages are fenced out; only the compaction machinery's
    #: own INFO/COMPACTION/REFLECTION writes are allowed.
    is_compacting = models.BooleanField(default=False, db_index=True)
    #: PK of the live ``compact_turn`` call (updated on retries).  The flag is
    #: cleared centrally when this call ends; the id makes that check exact.
    compacting_call_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    #: Session root shared by the triggering turn and its compaction fork.
    #: Used to tell compaction-owned writes from sibling turns.
    compacting_root_task_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    last_active_at = models.DateTimeField(null=True, blank=True)
    is_pinned = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    session_type = models.CharField(max_length=30, choices=SessionType.choices, default=SessionType.SESSION, db_index=True)

    parent_session = models.ForeignKey("self",on_delete=models.CASCADE,related_name="child_sessions",default=None,null=True,blank=True)
    parent_project = models.ForeignKey("server.Project",on_delete=models.SET_NULL,default=None,null=True,blank=True,related_name="child_sessions")
    latest_session_version = models.ForeignKey("server.SessionVersionModel",default=None,null=True,on_delete=models.CASCADE,related_name="related_newest_version")

    class Meta:
        # Session names must be unique *within a parent*, not globally: two
        # projects may each own a session called "research".  The old code
        # looked sessions up by name alone (see
        # ``AgentVersionModel.get_or_create_session``), so those two sessions
        # silently shared one row — one turn_count, one message chain.
        #
        # Scope: this covers every session with a non-NULL ``parent_session``
        # (all forks and subsessions, including every work-item executor).
        # MariaDB and SQLite treat NULLs as distinct in unique indexes, so
        # top-level sessions are not covered by the index itself — those are
        # kept correct by the scoped lookup, not by this constraint.
        constraints = [
            models.UniqueConstraint(
                fields=["name", "parent_session"],
                name="uniq_session_name_per_parent",
            ),
        ]

    @property
    def messages(self) -> QuerySet:
        """All messages belonging to this session across all versions."""
        return Message.objects.filter(session_version__session=self)

    @property
    def queries(self) -> QuerySet:
        """All queries belonging to this session across all versions."""
        return Query.objects.filter(session_version__session=self)


    def get_runtime(self) -> Session:
        """Return a runtime Session wrapper for this model."""
        from runtime.session.session import Session
        return Session(session_model=self)

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Mutual exclusivity: is_archived and is_active must never both be True.
        if getattr(self, "is_archived", False):
            self.is_active = False
        super().save(*args, **kwargs)
