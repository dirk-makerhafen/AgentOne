from __future__ import annotations
from pathlib import Path
from django.db import models
from server.models.queries.query import Query
from server.models.queries.response import Response
from django.db.models import QuerySet
from server.models.message import Message
from server.models.base_model import BaseModel

from typing import TYPE_CHECKING, List, Union
if TYPE_CHECKING:
    from runtime.agents.session import Session


class SessionModel(BaseModel):
    name  = models.CharField(max_length=255)
    turn_count  = models.IntegerField(default=0)
    unattended_turn_count  = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    parent_session = models.ForeignKey("self", on_delete=models.CASCADE, related_name="child_sessions", default=None, null=True, blank=True)
    latest_session_version = models.ForeignKey("server.SessionVersionModel", default=None, null=True, on_delete=models.CASCADE, related_name='related_newest_version')# for */someproject/.agentone/skills/ , null for global skill in ~/.agentone/skills

    @property
    def instance_home(self) -> Path:
        if self.agent and self.agent.pk and self.pk:
            return Path(f"/Users/Dirk/ai/AgentHome/agent:{self.agent.pk}/instance:{self.pk}")
        return Path()

    @property
    def messages(self)  -> Union[QuerySet, List[Message]]:
        return Message.objects.filter(session_version__session=self)

    @property
    def queries(self) -> Union[QuerySet, List[Query]]:
        return Query.objects.filter(session_version__session=self)

    @property
    def responses(self) -> Union[QuerySet, List[Response]]:
        return Response.objects.filter(session_version__session=self)

    def get_runtime(self) -> Session:
        from runtime.agents.session import Session
        return Session(session_model=self)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
