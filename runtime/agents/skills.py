from typing import List, Any, Dict, Union
from django.db.models import QuerySet

from server.models.skills.skill import SkillModel


class Skills():
    def __init__(self) -> None:
        pass
    def root(self) -> Union[QuerySet, List[SkillModel]]:
        return SkillModel.objects.filter(
            #parent_skill = None, 
            #parent_agent = None,
            #parent_project = None
        )