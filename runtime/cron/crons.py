from __future__ import annotations

from datetime import datetime
from typing import Any

from croniter import croniter
from django.db.models import QuerySet
from django.utils import timezone

from server.models.content import GenericContent, ContentType
from server.models.cron import Cronjob


class Cronjobs:
    """Query interface for Cronjob instances."""

    def __init__(self) -> None:
        pass

    def root(self) -> QuerySet[Cronjob]:
        """Return all cron jobs."""
        return Cronjob.objects.all()

    def active(self) -> QuerySet[Cronjob]:
        """Return only active cron jobs."""
        return Cronjob.objects.filter(is_active=True)

    def due(self) -> QuerySet[Cronjob]:
        """Return active cron jobs that are due to run now."""
        now = timezone.now()
        return Cronjob.objects.filter(
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
        pipe_names: list | None = None,
    ) -> Cronjob:
        """Create a new cron job with a GenericContent for the message."""
        message = None
        if message_content:
            message = GenericContent.objects.create(
                content=message_content,
                content_type=ContentType.TEXT,
            )
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
            pipe_names=pipe_names or [],
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
