from django.db.models import QuerySet

from server.models.skills.skill import SkillModel


class Skills:
    """Query interface for SkillModel instances."""

    def __init__(self) -> None:
        pass

    def root(self) -> QuerySet[SkillModel]:
        """Return all skills (filter placeholder preserved)."""
        return SkillModel.objects.filter()
