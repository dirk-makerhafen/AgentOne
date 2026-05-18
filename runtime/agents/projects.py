from typing import List, Any, Dict, Union
from django.db.models import QuerySet

from server.models.project import Project


class Projects():
    def __init__(self) -> None:
        pass
    
    def root(self) -> Union[QuerySet, List[Project]]:
        return Project.objects.all()
    
