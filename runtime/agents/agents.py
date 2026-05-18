from typing import List, Any, Dict, Union
from django.db.models import QuerySet

from runtime.agents.agent import Agent
from server.models.agents.agent import AgentModel


class Agents():
    def __init__(self) -> None:
        pass

    def root(self) -> Union[QuerySet, List[AgentModel]]:
        return AgentModel.objects.filter(
            parent_skill = None, 
            parent_agent = None,
            parent_project = None
        )
    
