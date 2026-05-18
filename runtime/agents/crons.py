from typing import List, Any, Dict, Union
from django.db.models import QuerySet

from server.models.cron import Cronjob


class Cronjobs():
    def __init__(self) -> None:
        pass
    def root(self) -> Union[QuerySet, List[Cronjob]]:
        return Cronjob.objects.filter(
            #parent_skill = None, 
            #parent_agent = None,
            #parent_project = None
        )