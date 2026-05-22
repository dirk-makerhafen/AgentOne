from django.db.models import QuerySet

from server.models.project import Project


class Projects:
    """Query interface for Project instances."""

    def __init__(self) -> None:
        pass

    def root(self) -> QuerySet[Project]:
        """Return all projects."""
        return Project.objects.all()
