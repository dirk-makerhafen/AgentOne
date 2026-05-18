from typing import List, Any, Dict, Union
from django.db.models import QuerySet

from server.models.sessions.session import SessionModel


class Sessions():
    def __init__(self) -> None:
        pass

    def root(self) -> Union[QuerySet, List[SessionModel]]:
        print("INSTANCES")

        i= SessionModel.objects.filter(
            #latest_session_version__agent_version__parent_skill = None, 
            #latest_session_version__agent_version__parent_agent = None,
            #latest_session_version__agent_version__parent_project = None
        )
        print(i)
        return i
    