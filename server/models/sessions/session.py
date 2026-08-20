from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models
from django.db.models import QuerySet

from server.models.base_model import BaseModel, Observables
from server.models.enums.session_enums import SessionType
from server.models.message import Message
from server.models.queries.query import Query

if TYPE_CHECKING:
    from runtime.session.session import Session


class SessionModel(BaseModel):
    """A conversation session that versions its state over time."""

    class SessionModelObservables(Observables):
        """Explicit observable keys for an SessionModel (IDE autocomplete)."""
        @property
        def child_sessions(self):
            return f"SessionModel.parent_session:{self.model.pk}"
        @property
        def messages(self):
            return f"Message.session:{self.model.pk}"
        @property
        def queries(self):
            return f"Query.session:{self.model.pk}"

    name = models.CharField(max_length=255)
    turn_count = models.IntegerField(default=0)
    unattended_turn_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    last_active_at = models.DateTimeField(null=True, blank=True)
    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    session_type = models.CharField(max_length=30, choices=SessionType.choices, default=SessionType.SESSION)

    parent_session = models.ForeignKey("self",on_delete=models.CASCADE,related_name="child_sessions",default=None,null=True,blank=True)
    parent_project = models.ForeignKey("server.Project",on_delete=models.SET_NULL,default=None,null=True,blank=True,related_name="child_sessions")
    latest_session_version = models.ForeignKey("server.SessionVersionModel",default=None,null=True,on_delete=models.CASCADE,related_name="related_newest_version")

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
        super().save(*args, **kwargs)
