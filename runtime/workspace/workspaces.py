from django.db.models import QuerySet

from server.models.workspace import WorkspaceModel


class Workspaces:
    """Query interface for WorkspaceModel instances."""

    def __init__(self) -> None:
        pass

    def root(self) -> QuerySet[WorkspaceModel]:
        """Return all workspaces."""
        return WorkspaceModel.objects.filter()
