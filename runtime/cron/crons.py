from django.db.models import QuerySet

from server.models.cron import Cronjob


class Cronjobs:
    """Query interface for Cronjob instances."""

    def __init__(self) -> None:
        pass

    def root(self) -> QuerySet[Cronjob]:
        """Return all cron jobs."""
        return Cronjob.objects.filter()
