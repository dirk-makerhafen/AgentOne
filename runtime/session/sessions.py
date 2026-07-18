from django.db.models import QuerySet

from server.models.sessions.session import SessionModel


class Sessions:
    """Query interface for SessionModel instances."""

    def __init__(self) -> None:
        pass

    def root(self) -> QuerySet[SessionModel]:
        """Return all sessions."""
        #return SessionModel.objects.filter(parent_session__isnull=True)
        return SessionModel.objects.filter()
