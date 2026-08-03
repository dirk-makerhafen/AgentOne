from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models
from django.db.models import QuerySet

from server.models.base_model import BaseModel
from server.models.message import Message
from server.models.queries.query import Query

if TYPE_CHECKING:
    from runtime.session.session import Session


class SessionModel(BaseModel):
    """A conversation session that versions its state over time."""

    name = models.CharField(max_length=255)
    turn_count = models.IntegerField(default=0)
    unattended_turn_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    parent_session = models.ForeignKey("self",on_delete=models.CASCADE,related_name="child_sessions",default=None,null=True,blank=True)
    parent_project = models.ForeignKey("server.Project",on_delete=models.SET_NULL,default=None,null=True,blank=True,related_name="child_sessions")
    latest_session_version = models.ForeignKey("server.SessionVersionModel",default=None,null=True,on_delete=models.CASCADE,related_name="related_newest_version")

    observable_fields = set([
        "pk",
        "parent_session",  
        "parent_project",
        "latest_session_version",                         
    ])

    @property
    def messages(self) -> QuerySet:
        """All messages belonging to this session across all versions."""
        return Message.objects.filter(session_version__session=self)

    @property
    def queries(self) -> QuerySet:
        """All queries belonging to this session across all versions."""
        return Query.objects.filter(session_version__session=self)

    @property
    def observable_keys(self):
        k = f"SessionModel:{self.pk}"
        k = f"SessionModel:{self.parent_session_pk}:child_sessions"
        k = f"Project:{self.parent_project_pk}:child_sessions"
        

        return set([
            "SessionModel",
            f"SessionModel.pk:{self.pk}",
            f"SessionModel.parent_session:{self.parent_session_pk}",
            f"SessionModel.parent_project:{self.parent_project_pk}",
        ])

    def get_runtime(self) -> Session:
        """Return a runtime Session wrapper for this model."""
        from runtime.session.session import Session
        return Session(session_model=self)

    def save(self, *args: Any, **kwargs: Any) -> None:
        super().save(*args, **kwargs)
