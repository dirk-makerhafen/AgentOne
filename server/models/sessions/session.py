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

    parent_session = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="child_sessions",
        default=None,
        null=True,
        blank=True,
    )
    latest_session_version = models.ForeignKey(
        "server.SessionVersionModel",
        default=None,
        null=True,
        on_delete=models.CASCADE,
        related_name="related_newest_version",
    )

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
