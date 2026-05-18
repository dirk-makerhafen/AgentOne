
from typing import List, Any, Dict, Union
from django.db.models import QuerySet

from server.models.workspace import WorkspaceModel

class Workspaces():
    def __init__(self) -> None:
        pass
    
    def root(self) -> Union[QuerySet, List[WorkspaceModel]]:
        return WorkspaceModel.objects.filter(
            #parent_skill = None, 
            #parent_agent = None,
            #parent_project = None
        )

